from __future__ import annotations

import socket
import subprocess
import tomllib
from pathlib import Path
from types import SimpleNamespace

import gradio as gr
import pytest
from langchain_core.messages import AIMessage

from ltc_benefit_agent.agent.config import AgentProvider
from ltc_benefit_agent.agent.service import AgentTurnResult
from ltc_benefit_agent.ui.app import (
    CSS,
    HEADER,
    HOW_TO,
    _updates,
    build_demo,
    ensure_port_available,
)
from ltc_benefit_agent.ui.controller import (
    GradioController,
    UiResponse,
    available_providers,
    provider_choices,
)


ROOT = Path(__file__).resolve().parents[1]


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


class EmptyReplyService:
    def send_message(self, thread_id: str, text: str) -> AgentTurnResult:
        del text
        return AgentTurnResult(thread_id, {"messages": []}, ())


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


def test_controller_reject_directs_user_to_visible_followup_input() -> None:
    service = FakeService()
    controller = GradioController(service_factory=lambda provider: service)  # type: ignore[arg-type]
    pending = controller.submit(
        session_id="session-a",
        provider_value="gemini",
        compare_legacy=False,
        text="資料已齊。",
        history=[],
    )
    rejected = controller.decide(
        session_id="session-a",
        provider_value="gemini",
        decision="reject",
        history=pending.history,
    )

    assert rejected.status == "草稿未發布。請在下方回答欄補充或修正資料。"
    assert not rejected.approval_visible


def test_space_only_exposes_cloud_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SPACE_ID", "owner/demo")
    assert available_providers() == (AgentProvider.GEMINI,)
    assert provider_choices() == [("雲端模式", "gemini")]


def test_space_metadata_and_install_entrypoint_are_complete() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.startswith("---\n")
    frontmatter = readme.split("---", 2)[1]
    for required in (
        "sdk: gradio",
        "sdk_version: 6.20.0",
        'python_version: "3.11"',
        "app_file: app.py",
        "fullWidth: true",
        "header: mini",
    ):
        assert required in frontmatter
    requirements_lines = (ROOT / "requirements.txt").read_text(
        encoding="utf-8"
    ).splitlines()
    active_requirements = [
        line for line in requirements_lines if line and not line.startswith("#")
    ]
    exported = subprocess.check_output(
        [
            "uv",
            "export",
            "--locked",
            "--format",
            "requirements.txt",
            "--no-dev",
            "--no-emit-project",
            "--no-hashes",
            "--no-annotate",
            "--no-header",
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    )
    assert active_requirements == exported.splitlines()

    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    locked_versions: dict[str, set[str]] = {}
    for package in lock["package"]:
        locked_versions.setdefault(package["name"], set()).add(package["version"])
    for line in exported.splitlines():
        requirement = line.split(" ; ", 1)[0]
        name, version = requirement.split("==", 1)
        assert version in locked_versions[name]
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'Path(__file__).resolve().parent / "src"' in app_source
    assert "sys.path.insert(0, str(SOURCE_ROOT))" in app_source


def test_empty_model_reply_separates_multiple_people() -> None:
    service = EmptyReplyService()
    controller = GradioController(service_factory=lambda provider: service)  # type: ignore[arg-type]
    response = controller.submit(
        session_id="session-a",
        provider_value="gemini",
        compare_legacy=False,
        text="兩位家人都需要評估",
        history=[],
    )

    assert response.history[-1]["role"] == "assistant"
    assert "不只一位家人" in response.history[-1]["content"]


def test_empty_model_reply_keeps_known_age_and_asks_actual_missing_info() -> None:
    service = EmptyReplyService()
    controller = GradioController(service_factory=lambda provider: service)  # type: ignore[arg-type]
    response = controller.submit(
        session_id="session-a",
        provider_value="gemini",
        compare_legacy=False,
        text="我阿公84歲，太老了不能騎機車，只能騎腳踏車，有攝護腺癌",
        history=[],
    )

    reply = response.history[-1]["content"]
    assert "84 歲" in reply
    assert "年齡或疾病名稱" in reply
    assert "洗澡" in reply and "如廁" in reply
    assert "先選" not in reply
    assert response.status == ""


def test_second_turn_accepts_gradio_text_content_blocks() -> None:
    service = EmptyReplyService()
    controller = GradioController(service_factory=lambda provider: service)  # type: ignore[arg-type]
    first = controller.submit(
        session_id="session-a",
        provider_value="gemini",
        compare_legacy=False,
        text="家人 84 歲，有攝護腺癌",
        history=[],
    )
    gradio_history = [
        {
            "role": item["role"],
            "content": [{"type": "text", "text": item["content"]}],
        }
        for item in first.history
    ]

    second = controller.submit(
        session_id="session-a",
        provider_value="gemini",
        compare_legacy=False,
        text="洗澡和穿衣需要協助，已持續 8 個月",
        history=gradio_history,
    )

    reply = second.history[-1]["content"]
    assert isinstance(reply, str)
    assert "原住民" in reply
    assert "住宿式機構" in reply


def test_demo_builds_without_loading_a_model() -> None:
    controller = GradioController(service_factory=lambda provider: FakeService())  # type: ignore[arg-type]
    demo = build_demo(controller)
    assert isinstance(demo, gr.Blocks)
    config = demo.get_config_file()
    chatbot = next(
        component
        for component in config["components"]
        if component.get("props", {}).get("label") == "對話紀錄"
    )
    assert chatbot["props"]["height"] == 320
    assert chatbot["props"]["show_label"] is False
    assert chatbot["props"]["buttons"] == ["copy_all"]
    conversation_section = next(
        component
        for component in config["components"]
        if component.get("props", {}).get("elem_id") == "conversation-section"
    )
    history_section = next(
        component
        for component in config["components"]
        if component.get("props", {}).get("elem_id") == "history-section"
    )
    current_question = next(
        component
        for component in config["components"]
        if component.get("props", {}).get("elem_id") == "current-question"
    )
    report_section = next(
        component
        for component in config["components"]
        if component.get("props", {}).get("elem_id") == "report-section"
    )
    onboarding_section = next(
        component
        for component in config["components"]
        if component.get("props", {}).get("elem_id") == "onboarding-section"
    )
    assert onboarding_section["props"]["visible"] is True
    assert conversation_section["props"]["visible"] is False
    assert history_section["props"]["visible"] is False
    assert report_section["props"]["visible"] is False
    assert current_question["props"]["value"] == ""
    assert any(
        component.get("props", {}).get("label") == "模型模式"
        for component in config["components"]
    )
    assert "長照 2.0 資格與補助初步試算" in HEADER
    assert "資格與金額由確定性工具計算" not in HEADER
    assert "CMS 未知不猜級" not in HEADER
    assert "金額由 Python 計算" not in HEADER
    assert "報告發布前先確認" not in HEADER
    assert "照這 4 步操作" in HOW_TO
    assert "可稽核" not in HEADER
    assert "radial-gradient" not in CSS
    assert "font-size: 19px" in CSS
    assert 'input:not([type="checkbox"])' in CSS
    assert 'body [role="option"]' in CSS
    assert "min-height: 90px" in CSS
    assert "同時顯示 2022 舊制" in str(config)
    assert "先描述這位家人的情況" in str(config)
    assert "直接回答上面的問題" in str(config)
    assert "送出回答" in str(config)
    assert "系統會根據你的回答繼續追問" in str(config)
    assert "請先說明家人的年齡" not in str(config)
    assert "進階設定（一般不用調整）" in str(config)
    assert "重新評估另一位家人" in str(config)
    assert "#history-section .gr-accordion > button.label-wrap" in CSS
    assert "font-size: 20px" in CSS
    assert "max-width: 920px" in CSS
    assert '#legacy-toggle label span' in CSS
    assert "font-size: 1.25rem" in CSS


def test_progressive_sections_only_appear_when_content_exists() -> None:
    empty = _updates(UiResponse([], "", "", "", False, "尚未開始"))
    assert empty[-4]["visible"] is True
    assert empty[-3]["visible"] is False
    assert empty[-2]["visible"] is False
    assert empty[-1]["visible"] is False

    conversation = _updates(
        UiResponse(
            [
                {"role": "user", "content": "家庭情況"},
                {"role": "assistant", "content": "請問生活協助需求？"},
            ],
            "",
            "",
            "",
            False,
            "",
        )
    )
    assert conversation[1] == "請問生活協助需求？"
    assert conversation[7]["visible"] is False
    assert conversation[-4]["visible"] is False
    assert conversation[-3]["visible"] is True
    assert conversation[-2]["visible"] is True
    assert conversation[-1]["visible"] is False

    report = _updates(
        UiResponse(
            [{"role": "assistant", "content": "草稿完成"}],
            REPORT,
            "明細",
            "來源",
            True,
            "待核准",
        )
    )
    assert report[1] == "待核准"
    assert report[-4]["visible"] is False
    assert report[-3]["visible"] is False
    assert report[-2]["visible"] is True
    assert report[-1]["visible"] is True


def test_port_check_never_closes_existing_listener() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        with pytest.raises(RuntimeError, match="已被占用"):
            ensure_port_available("127.0.0.1", port)
        assert listener.fileno() >= 0
