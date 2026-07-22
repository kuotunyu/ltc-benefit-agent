from __future__ import annotations

import socket
from types import SimpleNamespace

import gradio as gr
import pytest
from langchain_core.messages import AIMessage

from ltc_benefit_agent.agent.config import AgentProvider
from ltc_benefit_agent.agent.service import AgentTurnResult
from ltc_benefit_agent.ui.app import build_demo, ensure_port_available
from ltc_benefit_agent.ui.controller import (
    GradioController,
    available_providers,
    provider_choices,
)


REPORT = """# 長照服務資格與補助初步建議書

## 估算額度表

| 項目 | 金額 |
|---|---:|
| 合計自付 | NT$ 1,920 |

## 引用來源

- [現行辦法](https://law.moj.gov.tw/)

## 免責聲明

僅供參考。
"""


class FakeService:
    def __init__(self) -> None:
        self.messages: list[str] = []
        self.decisions: list[str] = []

    def send_message(self, thread_id: str, text: str) -> AgentTurnResult:
        self.messages.append(f"{thread_id}:{text}")
        interrupt = SimpleNamespace(
            value={
                "action_requests": [
                    {
                        "name": "publish_report",
                        "args": {"report_id": "report-1", "report_markdown": REPORT},
                    }
                ]
            }
        )
        return AgentTurnResult(thread_id, {"messages": []}, (interrupt,))

    def decide(self, thread_id: str, decision: str) -> AgentTurnResult:
        self.decisions.append(f"{thread_id}:{decision}")
        content = REPORT if decision == "approve" else "已拒絕"
        metadata = (
            {"deterministic_published_report": True}
            if decision == "approve"
            else {}
        )
        return AgentTurnResult(
            thread_id,
            {"messages": [AIMessage(content=content, additional_kwargs=metadata)]},
            (),
        )


def test_controller_keeps_sessions_isolated_and_masks_chat_echo() -> None:
    services: list[FakeService] = []

    def factory(provider: AgentProvider) -> FakeService:
        del provider
        service = FakeService()
        services.append(service)
        return service

    controller = GradioController(service_factory=factory)  # type: ignore[arg-type]
    first = controller.submit(
        session_id="session-a",
        provider_value="gemini",
        compare_legacy=False,
        text="我叫王小明，電話 0912-345-678，資料已齊。",
        history=[],
    )
    second = controller.submit(
        session_id="session-b",
        provider_value="gemini",
        compare_legacy=True,
        text="另一個家庭的資料已齊。",
        history=[],
    )

    assert len(services) == 2
    assert "王小明" not in first.history[0]["content"]
    assert "0912-345-678" not in first.history[0]["content"]
    assert "LEGACY_2022" not in services[0].messages[0]
    assert "LEGACY_2022" in services[1].messages[0]
    assert first.approval_visible and second.approval_visible


def test_controller_approval_exposes_same_preview_and_panels() -> None:
    service = FakeService()
    controller = GradioController(service_factory=lambda provider: service)  # type: ignore[arg-type]
    pending = controller.submit(
        session_id="session-a",
        provider_value="gemini",
        compare_legacy=False,
        text="資料已齊。",
        history=[],
    )
    approved = controller.decide(
        session_id="session-a",
        provider_value="gemini",
        decision="approve",
        history=pending.history,
    )

    assert approved.preview == pending.preview == REPORT
    assert "合計自付" in approved.details
    assert "現行辦法" in approved.sources
    assert approved.history[-1]["content"] == REPORT
    assert not approved.approval_visible


def test_space_only_exposes_cloud_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPACE_ID", "owner/demo")
    assert available_providers() == (AgentProvider.GEMINI,)
    assert provider_choices() == [("雲端模式", "gemini")]


def test_demo_builds_without_loading_a_model() -> None:
    controller = GradioController(service_factory=lambda provider: FakeService())  # type: ignore[arg-type]
    demo = build_demo(controller)
    assert isinstance(demo, gr.Blocks)
    config = demo.get_config_file()
    assert any(component.get("props", {}).get("label") == "對話紀錄" for component in config["components"])
    assert any(component.get("props", {}).get("label") == "模型模式" for component in config["components"])


def test_port_check_never_closes_existing_listener() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        with pytest.raises(RuntimeError, match="已被占用"):
            ensure_port_available("127.0.0.1", port)
        assert listener.fileno() >= 0
