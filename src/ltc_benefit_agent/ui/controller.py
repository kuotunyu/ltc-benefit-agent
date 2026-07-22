"""與 Gradio 元件解耦的 session、HITL 與顯示資料控制。"""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock

from ltc_benefit_agent.agent.config import AgentProvider, AgentSettings
from ltc_benefit_agent.agent.factory import build_agent_runtime
from ltc_benefit_agent.agent.privacy import redact_text
from ltc_benefit_agent.agent.service import BenefitAgentService


ChatHistory = list[dict[str, str]]
ServiceFactory = Callable[[AgentProvider], BenefitAgentService]


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
        next_history = list(history or [])
        if changed:
            next_history = []
            next_history.append(
                {"role": "assistant", "content": "模型模式已切換，這是一段新的評估對話。"}
            )
        next_history.append({"role": "user", "content": redact_text(cleaned)})
        effective_text = cleaned
        if compare_legacy:
            effective_text += (
                "\n\n[介面明確選項：使用者要求現制結果並列 LEGACY_2022 舊制比較。]"
            )
        turn = service.send_message(session_id, effective_text)
        if turn.awaiting_approval:
            preview, details, sources = _report_panels(turn.pending_report_preview)
            next_history.append(
                {
                    "role": "assistant",
                    "content": "確定性報告草稿已完成。請先到右側校閱，再選擇核准或拒絕。",
                }
            )
            return UiResponse(
                next_history,
                preview,
                details,
                sources,
                True,
                "🟠 等待人工確認；草稿尚未發布。",
            )
        next_history.append({"role": "assistant", "content": turn.latest_text})
        return UiResponse(
            next_history,
            "",
            "",
            "",
            False,
            "🟢 對話進行中；尚未產生最終報告。",
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
        next_history = list(history or [])
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
                "✅ 已核准；最終報告與校閱草稿逐字一致。",
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
            "⚪ 草稿已拒絕；可繼續修正對話。",
        )

    def clear(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)
