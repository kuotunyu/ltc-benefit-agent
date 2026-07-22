"""與 Gradio 元件解耦的 session、HITL 與顯示資料控制。"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock

from ltc_benefit_agent.agent.config import AgentProvider, AgentSettings
from ltc_benefit_agent.agent.factory import build_agent_runtime
from ltc_benefit_agent.agent.privacy import redact_text
from ltc_benefit_agent.agent.service import BenefitAgentService
from ltc_benefit_agent.agent.workflow import (
    CURRENT_WITH_HISTORICAL_COMPARISON_DIRECTIVE,
)


ChatHistory = list[dict[str, object]]
ServiceFactory = Callable[[AgentProvider], BenefitAgentService]

_AGE_PATTERN = re.compile(r"(?<!\d)(\d{1,3})\s*歲")
_MULTIPLE_PEOPLE_PATTERN = re.compile(
    r"(?:兩|2)\s*(?:位|人|個)|阿公.{0,8}阿嬤|阿嬤.{0,8}阿公|父母|爸媽"
)
_DAILY_ACTIVITY_PATTERN = re.compile(
    r"洗澡|沐浴|穿衣|吃飯|進食|行走|走路|起身|上下床|如廁|上廁所"
)
_ASSISTANCE_PATTERN = re.compile(r"需要|協助|幫忙|無法|不能|不用|可以自己")
_DURATION_PATTERN = re.compile(
    r"(?<!\d)\d+\s*(?:個)?(?:月|年)|半年|一年|兩年|持續多久"
)


def _content_text(content: object) -> str:
    """將 Gradio 6 的文字 content blocks 收斂成 controller 使用的純文字。"""

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(part for part in parts if part)
    return ""


def _normalize_history(history: ChatHistory | None) -> ChatHistory:
    normalized: ChatHistory = []
    for item in history or []:
        role = item.get("role")
        if role not in {"user", "assistant", "system"}:
            continue
        normalized.append({"role": role, "content": _content_text(item.get("content"))})
    return normalized


def _user_history_text(history: ChatHistory) -> str:
    return "\n".join(
        _content_text(item.get("content"))
        for item in history
        if item.get("role") == "user"
    )


def _known_age(history_text: str) -> int | None:
    ages = [int(value) for value in _AGE_PATTERN.findall(history_text)]
    plausible = [age for age in ages if 0 <= age <= 120]
    return plausible[-1] if plausible else None


def _empty_reply_guidance(current_text: str, history: ChatHistory) -> str:
    """模型沒有顯示文字時，依已知資料提出不涉及資格計算的下一問。"""

    if _MULTIPLE_PEOPLE_PATTERN.search(current_text):
        return (
            "我看到你提到不只一位家人。為了避免資料混在一起，請先選一位，"
            "再告訴我這位家人的年齡與目前需要他人協助的生活事項。"
        )

    history_text = _user_history_text(history)
    age = _known_age(history_text)
    has_daily_activity = bool(
        _DAILY_ACTIVITY_PATTERN.search(history_text)
        and _ASSISTANCE_PATTERN.search(history_text)
    )
    has_duration = bool(_DURATION_PATTERN.search(history_text))

    if age is None:
        return (
            "我已收到你描述的情況。請再告訴我這位家人的年齡，以及洗澡、"
            "穿衣、吃飯、起身走動或如廁時，哪些需要別人協助。"
        )
    if not has_daily_activity:
        return (
            f"收到，已記下這位家人 {age} 歲和你描述的健康狀況。長照初篩不是"
            "只看年齡或疾病名稱，還要看日常生活功能。請問他在洗澡、穿衣、"
            "吃飯、起身走動或如廁時，哪些需要別人協助？大約持續多久？"
        )
    if not has_duration:
        return (
            f"收到，已記下這位家人 {age} 歲和生活協助需求。請問這些情況已"
            "持續多久？若不知道確切時間，可以回答大約幾個月或幾年。"
        )
    return (
        "收到，已記下年齡、生活協助需求和持續時間。接下來請問：是否為"
        "原住民、領有身心障礙證明、確診失智或 PAC 個案？目前住在家中、"
        "團體家屋還是住宿式機構？不知道的項目可以直接回答「不知道」。"
    )


@dataclass(frozen=True, slots=True)
class UiResponse:
    history: ChatHistory
    preview: str
    details: str
    sources: str
    approval_visible: bool
    status: str


@dataclass(slots=True)
class _Session:
    provider: AgentProvider
    service: BenefitAgentService


def _default_service_factory(provider: AgentProvider) -> BenefitAgentService:
    settings = AgentSettings.from_env(provider=provider)
    return BenefitAgentService(build_agent_runtime(settings=settings))


def available_providers(*, is_space: bool | None = None) -> tuple[AgentProvider, ...]:
    if is_space is None:
        is_space = bool(os.getenv("SPACE_ID"))
    if is_space:
        return (AgentProvider.GEMINI,)
    return tuple(AgentProvider)


def provider_choices(*, is_space: bool | None = None) -> list[tuple[str, str]]:
    labels = {
        AgentProvider.GEMINI: "雲端模式",
        AgentProvider.F1_OLLAMA: "F1 3B 地端模式",
        AgentProvider.GEMMA3_BASELINE: "12B 地端基準（相容 adapter）",
    }
    return [(labels[item], item.value) for item in available_providers(is_space=is_space)]


def _section(markdown: str, heading: str) -> str:
    marker = f"## {heading}"
    start = markdown.find(marker)
    if start < 0:
        return ""
    next_heading = markdown.find("\n## ", start + len(marker))
    return markdown[start:] if next_heading < 0 else markdown[start:next_heading]


def _report_panels(markdown: str | None) -> tuple[str, str, str]:
    if not markdown:
        return "", "", ""
    details = _section(markdown, "估算額度表") or _section(
        markdown, "CMS 未知：僅提供額度參考"
    )
    return markdown, details, _section(markdown, "引用來源")


class GradioController:
    def __init__(self, service_factory: ServiceFactory | None = None) -> None:
        self._service_factory = service_factory or _default_service_factory
        self._sessions: dict[str, _Session] = {}
        self._lock = Lock()

    def _get_service(
        self, session_id: str, provider: AgentProvider
    ) -> tuple[BenefitAgentService, bool]:
        if not session_id:
            raise ValueError("無法取得介面 session id")
        if provider not in available_providers():
            raise ValueError("此執行環境不允許所選 provider")
        with self._lock:
            current = self._sessions.get(session_id)
            changed = current is not None and current.provider is not provider
            if current is None or changed:
                current = _Session(provider, self._service_factory(provider))
                self._sessions[session_id] = current
        return current.service, changed

    def submit(
        self,
        *,
        session_id: str,
        provider_value: str,
        compare_legacy: bool,
        text: str,
        history: ChatHistory | None,
    ) -> UiResponse:
        cleaned = text.strip()
        if not cleaned:
            raise ValueError("請先輸入家人的情況")
        provider = AgentProvider(provider_value)
        service, changed = self._get_service(session_id, provider)
        next_history = _normalize_history(history)
        if changed:
            next_history = []
            next_history.append(
                {"role": "assistant", "content": "模型模式已切換，這是一段新的評估對話。"}
            )
        next_history.append({"role": "user", "content": redact_text(cleaned)})
        effective_text = cleaned
        if compare_legacy:
            effective_text += (
                f"\n\n{CURRENT_WITH_HISTORICAL_COMPARISON_DIRECTIVE}"
            )
        turn = service.send_message(session_id, effective_text)
        if turn.awaiting_approval:
            preview, details, sources = _report_panels(turn.pending_report_preview)
            next_history.append(
                {
                    "role": "assistant",
                    "content": (
                        "確定性報告草稿已完成。請檢查下方內容，再選擇核准或退回修正。"
                    ),
                }
            )
            return UiResponse(
                next_history,
                preview,
                details,
                sources,
                True,
                "下一步：請檢查下方報告草稿，再選擇核准或退回修正。",
            )
        assistant_text = turn.latest_text.strip() or _empty_reply_guidance(
            cleaned, next_history
        )
        next_history.append({"role": "assistant", "content": assistant_text})
        return UiResponse(
            next_history,
            "",
            "",
            "",
            False,
            "",
        )

    def decide(
        self,
        *,
        session_id: str,
        provider_value: str,
        decision: str,
        history: ChatHistory | None,
    ) -> UiResponse:
        provider = AgentProvider(provider_value)
        service, changed = self._get_service(session_id, provider)
        if changed:
            raise ValueError("模型模式已切換，原草稿不能在新 session 核准")
        next_history = _normalize_history(history)
        turn = service.decide(session_id, decision)  # type: ignore[arg-type]
        if decision == "approve":
            report = turn.latest_text
            next_history.append({"role": "assistant", "content": report})
            preview, details, sources = _report_panels(report)
            return UiResponse(
                next_history,
                preview,
                details,
                sources,
                False,
                "報告已核准；發布內容與校閱草稿逐字一致。",
            )
        next_history.append(
            {
                "role": "assistant",
                "content": "草稿已拒絕，沒有發布最終報告。請補充或修正資料後再試一次。",
            }
        )
        return UiResponse(
            next_history,
            "",
            "",
            "",
            False,
            "草稿未發布。請在下方回答欄補充或修正資料。",
        )

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
