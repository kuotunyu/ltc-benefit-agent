"""多輪 thread、PII 邊界與 HITL resume 的應用服務。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from threading import Lock
from typing import Any, Literal, Mapping

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.types import Command

from .factory import AgentRuntime
from .intake import merge_explicit_case_facts
from .privacy import redact_text, redact_value


Decision = Literal["approve", "reject"]
_UNVERIFIED_AMOUNT_PATTERN = re.compile(
    r"(?:NT\s*\$|新臺幣|\d[\d,]*(?:\.\d+)?\s*元|\d+(?:\.\d+)?\s*%)",
    re.IGNORECASE,
)
_UNVERIFIED_AMOUNT_MESSAGE = (
    "系統沒有採用模型自行產生、尚未經工具驗證的金額。"
    "請繼續回答尚未補齊的資料；若要試算，請提供正式 CMS、福利身分類別、"
    "是否有外籍看護與預計服務費。"
)


def _message_text(message: BaseMessage) -> str:
    if isinstance(message.content, str):
        return message.content
    parts: list[str] = []
    for block in message.content_blocks:
        if block.get("type") != "text":
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text)
    return "".join(parts)


@dataclass(frozen=True, slots=True)
class AgentTurnResult:
    thread_id: str
    state: Mapping[str, Any]
    interrupts: tuple[Any, ...]

    @property
    def awaiting_approval(self) -> bool:
        return bool(self.interrupts)

    @property
    def pending_report_preview(self) -> str | None:
        for interrupt in self.interrupts:
            value = getattr(interrupt, "value", {})
            for request in value.get("action_requests", []):
                if request.get("name") == "publish_report":
                    arguments = request.get("args", request.get("arguments", {}))
                    return arguments.get("report_markdown")
        return None

    @property
    def latest_text(self) -> str:
        preview = self.pending_report_preview
        if preview is not None:
            if "CMS 未知：僅提供額度參考" in preview:
                return (
                    "資格初篩報告草稿已產生；目前無須再補原住民、身障、失智或 PAC "
                    "資料。因尚未有正式 CMS（照管中心核定的長照需要等級），目前只提供額度參考與 1966 申請指引。"
                    "請檢查草稿後決定是否核准。"
                )
            return "補助試算報告草稿已產生，請檢查資格與金額後決定是否核准。"
        messages = self.state.get("messages", [])
        for message in reversed(messages):
            if isinstance(message, BaseMessage) and message.type in {"ai", "tool"}:
                text = _message_text(message)
                if text:
                    is_published_report = bool(
                        isinstance(message, AIMessage)
                        and message.additional_kwargs.get(
                            "deterministic_published_report", False
                        )
                    )
                    if (
                        isinstance(message, AIMessage)
                        and not is_published_report
                        and _UNVERIFIED_AMOUNT_PATTERN.search(text)
                    ):
                        return _UNVERIFIED_AMOUNT_MESSAGE
                    return text
        return ""


class BenefitAgentService:
    def __init__(self, runtime: AgentRuntime) -> None:
        self.runtime = runtime
        self._pending_previews: dict[str, str] = {}
        self._published_reports: dict[str, str] = {}
        self._pending_lock = Lock()

    @staticmethod
    def _config(thread_id: str) -> dict[str, dict[str, str]]:
        if not thread_id.strip():
            raise ValueError("thread_id 不得為空")
        return {"configurable": {"thread_id": thread_id}}

    @staticmethod
    def _normalize_result(thread_id: str, result: Any) -> AgentTurnResult:
        state = getattr(result, "value", result)
        interrupts = tuple(getattr(result, "interrupts", ()))
        return AgentTurnResult(
            thread_id=thread_id,
            state=redact_value(state),
            interrupts=interrupts,
        )

    def send_message(self, thread_id: str, text: str) -> AgentTurnResult:
        sanitized = redact_text(text)
        config = self._config(thread_id)
        snapshot = self.runtime.graph.get_state(config)
        previous = getattr(snapshot, "values", {})
        previous = previous if isinstance(previous, Mapping) else {}
        eligibility, copay = merge_explicit_case_facts(
            sanitized,
            previous_eligibility=previous.get("case_explicit_eligibility_facts"),
            previous_copay=previous.get("case_explicit_copay_facts"),
        )
        self.runtime.audit.record(
            "user_turn", payload={"thread_id": thread_id, "character_count": len(sanitized)}
        )
        result = self.runtime.graph.invoke(
            {
                "messages": [{"role": "user", "content": sanitized}],
                "case_explicit_eligibility_facts": eligibility,
                "case_explicit_copay_facts": copay,
            },
            config=config,
            version="v2",
        )
        normalized = self._normalize_result(thread_id, result)
        if normalized.awaiting_approval:
            preview = normalized.pending_report_preview
            if preview is not None:
                with self._pending_lock:
                    self._pending_previews[thread_id] = preview
                    self._published_reports.pop(thread_id, None)
        return normalized

    @staticmethod
    def _published_result(thread_id: str, report: str) -> AgentTurnResult:
        return AgentTurnResult(
            thread_id=thread_id,
            state={
                "messages": [
                    AIMessage(
                        content=report,
                        additional_kwargs={"deterministic_published_report": True},
                    )
                ]
            },
            interrupts=(),
        )

    def decide(self, thread_id: str, decision: Decision) -> AgentTurnResult:
        if decision not in {"approve", "reject"}:
            raise ValueError("decision 只允許 approve 或 reject")
        with self._pending_lock:
            preview = self._pending_previews.get(thread_id)
            published = self._published_reports.get(thread_id)
        if preview is None:
            # 瀏覽器若因網路或 UI 更新失敗重送 approve，回傳第一次已發布的
            # 完整原文；不可再次 resume HITL，也不應讓 Gradio 顯示通用錯誤。
            if decision == "approve" and published is not None:
                return self._published_result(thread_id, published)
            raise ValueError("此 thread 沒有待確認的完整報告")
        self.runtime.audit.record(
            "human_decision", payload={"thread_id": thread_id, "decision": decision}
        )
        result = self.runtime.graph.invoke(
            Command(resume={"decisions": [{"type": decision}]}),
            config=self._config(thread_id),
            version="v2",
        )
        normalized = self._normalize_result(thread_id, result)
        with self._pending_lock:
            self._pending_previews.pop(thread_id, None)
            if decision == "approve":
                self._published_reports[thread_id] = preview
        if decision == "reject":
            return normalized

        # publish_report 已逐字驗證草稿；對外回傳直接使用人類看到的版本，
        # 不讓核准後的模型摘要或改寫成為最終報告。
        state = dict(normalized.state)
        messages = list(state.get("messages", []))
        messages.append(
            AIMessage(
                content=preview,
                additional_kwargs={"deterministic_published_report": True},
            )
        )
        state["messages"] = messages
        return AgentTurnResult(
            thread_id=thread_id,
            state=state,
            # resume 後的人類決策已完成；部分 provider adapter 仍會回帶歷史
            # interrupt metadata，不應讓它覆蓋剛附上的逐字核准報告。
            interrupts=(),
        )
