from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from pydantic import Field

from ltc_benefit_agent.agent.config import AgentProvider, AgentSettings
from ltc_benefit_agent.agent.factory import build_agent_runtime, build_chat_model
from ltc_benefit_agent.agent.privacy import SafeAuditLogger, redact_text
from ltc_benefit_agent.agent.reports import (
    ReportPublicationRejected,
    ReportRegistry,
    render_report,
)
from ltc_benefit_agent.agent.service import AgentTurnResult, BenefitAgentService
from ltc_benefit_agent.agent.toolset import build_tool_bundle
from ltc_benefit_agent.tools.copay import WelfareCategory
from ltc_benefit_agent.tools.eligibility import EligibilityInput, ResidenceStatus
from ltc_benefit_agent.tools.rules import RuleVersion


COMPLETE_REPORT_ARGS: dict[str, Any] = {
    "age": 70,
    "indigenous": False,
    "has_disability_certificate": False,
    "has_dementia_diagnosis": False,
    "is_pac_case": False,
    "has_functional_impairment": True,
    "impairment_duration_months": 12,
    "residence_status": "COMMUNITY",
    "official_cms_level": 2,
    "welfare_category": "THIRD",
    "has_foreign_caregiver": False,
    "planned_spend": 20_000,
    "rule_version": "CURRENT_2026_07",
    "compare_legacy": False,
}


class ScriptedBenefitModel(BaseChatModel):
    """不含自然語言推理，只用來驗證 LangGraph tool/HITL wiring。"""

    seen_batches: list[tuple[BaseMessage, ...]] = Field(default_factory=list)
    bound_tool_names: list[str] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted-benefit-test-model"

    def bind_tools(
        self,
        tools: Sequence[BaseTool | dict[str, Any]],
        *,
        tool_choice: str | None = None,
        **kwargs: Any,
    ) -> "ScriptedBenefitModel":
        del tool_choice, kwargs
        self.bound_tool_names = [
            tool.name if isinstance(tool, BaseTool) else str(tool.get("name"))
            for tool in tools
        ]
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        self.seen_batches.append(tuple(messages))
        last = messages[-1]
        if isinstance(last, HumanMessage):
            keys = (
                "age",
                "indigenous",
                "has_disability_certificate",
                "has_dementia_diagnosis",
                "is_pac_case",
                "has_functional_impairment",
                "impairment_duration_months",
                "residence_status",
                "official_cms_level",
                "rule_version",
            )
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "eligibility_check",
                        "args": {key: COMPLETE_REPORT_ARGS[key] for key in keys},
                        "id": "call-1",
                    }
                ],
            )
        elif isinstance(last, ToolMessage) and last.name == "eligibility_check":
            args = {
                key: COMPLETE_REPORT_ARGS[key]
                for key in (
                    "welfare_category",
                    "has_foreign_caregiver",
                    "planned_spend",
                    "rule_version",
                )
            }
            args["cms_level"] = COMPLETE_REPORT_ARGS["official_cms_level"]
            message = AIMessage(
                content="",
                tool_calls=[
                    {"name": "copay_estimate", "args": args, "id": "call-2"}
                ],
            )
        elif isinstance(last, ToolMessage) and last.name == "copay_estimate":
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "build_report_draft",
                        "args": COMPLETE_REPORT_ARGS,
                        "id": "call-3",
                    }
                ],
            )
        elif isinstance(last, ToolMessage) and last.name == "build_report_draft":
            draft = json.loads(str(last.content))
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "publish_report",
                        "args": {
                            "report_id": draft["report_id"],
                            "report_markdown": draft["markdown"],
                        },
                        "id": "call-4",
                    }
                ],
            )
        elif isinstance(last, ToolMessage) and last.name == "publish_report":
            message = AIMessage(content=str(last.content))
        else:  # pragma: no cover - exposes unexpected LangGraph transitions
            raise AssertionError(f"unexpected last message: {last!r}")
        return ChatResult(generations=[ChatGeneration(message=message)])


class ScriptedQuestionModel(BaseChatModel):
    """驗證 checkpointer 保存多輪脈絡；問題內容本身不交給模型判分。"""

    @property
    def _llm_type(self) -> str:
        return "scripted-question-test-model"

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> "ScriptedQuestionModel":
        del tools, kwargs
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        user_turns = sum(isinstance(message, HumanMessage) for message in messages)
        content = "請問家人的年齡？" if user_turns == 1 else "是否具有原住民身分？"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


def settings() -> AgentSettings:
    return AgentSettings(
        provider=AgentProvider.GEMINI,
        gemini_model="offline-fake-model",
        ollama_f1_model="ltc-f1:q4_k_m",
        ollama_baseline_model="gemma3:12b",
        ollama_base_url="http://127.0.0.1:11434",
        is_space=False,
    )


def test_redaction_covers_supported_taiwan_pii() -> None:
    original = "我叫王小明，身分證 A123456789，手機 0912-345-678，市話 02-23456789"
    redacted = redact_text(original)
    for secret in ("王小明", "A123456789", "0912-345-678", "02-23456789"):
        assert secret not in redacted
    assert redacted.count("[REDACTED_") == 4
    official_url = "https://law.moj.gov.tw/LawGetFile.ashx?FileId=0000398330&lan=C"
    assert redact_text(official_url) == official_url


def test_unapproved_model_money_is_blocked_but_published_report_is_returned() -> None:
    unsafe = AgentTurnResult(
        "thread-unsafe",
        {"messages": [AIMessage(content="估算自付 NT$ 1,920，比例 16%。")]},
        (),
    )
    assert "1,920" not in unsafe.latest_text
    assert "未經確定性報告工具" in unsafe.latest_text

    report = "# 已核准報告\n\n合計自付 NT$ 1,920"
    published = AgentTurnResult(
        "thread-published",
        {
            "messages": [
                AIMessage(
                    content=report,
                    additional_kwargs={"deterministic_published_report": True},
                )
            ]
        },
        (),
    )
    assert published.latest_text == report


def test_full_create_agent_flow_masks_pii_and_waits_for_exact_approval() -> None:
    model = ScriptedBenefitModel()
    audit = SafeAuditLogger()
    runtime = build_agent_runtime(settings=settings(), model=model, audit=audit)
    service = BenefitAgentService(runtime)

    pii = "我叫王小明，A123456789，電話 0912-345-678。其餘資料已填好。"
    pending = service.send_message("thread-a", pii)

    assert pending.awaiting_approval
    preview = pending.pending_report_preview
    assert preview is not None, repr(pending.interrupts)
    assert preview.startswith("# 長照服務資格與補助初步建議書")
    assert "NT$ 10,020" in preview
    assert "NT$ 1,603" in preview
    assert "NT$ 11,583" in preview
    assert "王小明" not in preview

    model_inputs = "\n".join(
        str(message.content)
        for batch in model.seen_batches
        for message in batch
        if isinstance(message, HumanMessage)
    )
    assert "王小明" not in model_inputs
    assert "A123456789" not in model_inputs
    assert "0912-345-678" not in model_inputs

    assert not any(
        event.tool_name == "publish_report" and event.event == "tool_result"
        for event in audit.snapshot()
    )

    approved = service.decide("thread-a", "approve")
    assert not approved.awaiting_approval
    assert approved.latest_text == preview

    log_text = repr(audit.snapshot())
    for secret in ("王小明", "A123456789", "0912-345-678"):
        assert secret not in log_text
    assert "tool_call" in log_text
    assert "tool_result" in log_text
    assert "human_decision" in log_text


def test_reject_does_not_publish_report() -> None:
    model = ScriptedBenefitModel()
    audit = SafeAuditLogger()
    service = BenefitAgentService(
        build_agent_runtime(settings=settings(), model=model, audit=audit)
    )
    pending = service.send_message("thread-reject", "資料已填好")
    assert pending.awaiting_approval

    rejected = service.decide("thread-reject", "reject")
    assert not rejected.awaiting_approval
    assert rejected.latest_text != pending.pending_report_preview
    assert not any(
        event.tool_name == "publish_report" and event.event == "tool_result"
        for event in audit.snapshot()
    )


def test_multiturn_thread_keeps_question_order_and_isolates_new_thread() -> None:
    service = BenefitAgentService(
        build_agent_runtime(settings=settings(), model=ScriptedQuestionModel())
    )
    first = service.send_message("thread-one", "想申請長照")
    second = service.send_message("thread-one", "70 歲")
    isolated = service.send_message("thread-two", "另一位家人")
    assert first.latest_text == "請問家人的年齡？"
    assert second.latest_text == "是否具有原住民身分？"
    assert isolated.latest_text == "請問家人的年齡？"


def test_report_registry_rejects_model_rewrite() -> None:
    registry = ReportRegistry()
    draft = registry.register("政府給付 NT$ 8,417")
    assert registry.verify_and_publish(draft.report_id, draft.markdown) == draft.markdown
    with pytest.raises(ReportPublicationRejected, match="不一致"):
        registry.verify_and_publish(draft.report_id, "政府給付 NT$ 8,418")
    with pytest.raises(ReportPublicationRejected, match="未知"):
        registry.verify_and_publish("unknown-report-id", draft.markdown)


def test_unknown_cms_only_renders_reference_table() -> None:
    report = render_report(
        eligibility_input=EligibilityInput(
            age=70,
            indigenous=False,
            has_disability_certificate=False,
            has_dementia_diagnosis=False,
            is_pac_case=False,
            has_functional_impairment=True,
            impairment_duration_months=6,
            residence_status=ResidenceStatus.COMMUNITY,
            official_cms_level=None,
            rule_version=RuleVersion.CURRENT_2026_07,
        ),
        welfare_category=WelfareCategory.THIRD,
        has_foreign_caregiver=False,
        planned_spend=20_000,
    )
    assert "CMS 未知：僅提供額度參考" in report
    assert "不做個人化試算" in report
    assert "| 8 | NT$ 36,180 | NT$ 10,854 |" in report
    assert "政府給付" not in report
    assert "合計自付" not in report


def test_current_report_can_explicitly_compare_legacy_snapshot() -> None:
    report = render_report(
        eligibility_input=EligibilityInput(
            age=49,
            indigenous=False,
            has_disability_certificate=False,
            has_dementia_diagnosis=True,
            is_pac_case=False,
            has_functional_impairment=True,
            impairment_duration_months=10,
            residence_status=ResidenceStatus.COMMUNITY,
            official_cms_level=None,
            rule_version=RuleVersion.CURRENT_2026_07,
        ),
        welfare_category=None,
        has_foreign_caregiver=None,
        planned_spend=None,
        compare_legacy=True,
    )
    assert "`CURRENT_2026_07`" in report
    assert "## 舊制比較" in report
    assert "`LEGACY_2022` 初篩：`PRELIMINARY_CRITERIA_NOT_MET`" in report


def test_tools_reject_invalid_money_arguments_without_llm_math() -> None:
    tools = {item.name: item for item in build_tool_bundle().tools}
    eligibility_schema = tools["eligibility_check"].args_schema.model_json_schema()
    assert "COMMUNITY" in eligibility_schema["properties"]["residence_status"][
        "description"
    ]
    assert "false" in eligibility_schema["properties"]["is_pac_case"]["description"]
    schema = tools["copay_estimate"].args_schema.model_json_schema()
    assert "不可省略" in schema["properties"]["has_foreign_caregiver"]["description"]
    assert schema["properties"]["welfare_category"]["enum"] == [
        "FIRST",
        "SECOND",
        "THIRD",
    ]
    with pytest.raises(ValueError):
        tools["copay_estimate"].invoke(
            {
                "cms_level": 9,
                "welfare_category": "THIRD",
                "has_foreign_caregiver": False,
                "planned_spend": 10_000,
            }
        )


def test_space_rejects_ollama_provider() -> None:
    blocked = AgentSettings(
        provider=AgentProvider.F1_OLLAMA,
        gemini_model="cloud-model",
        ollama_f1_model="local-model",
        ollama_baseline_model="baseline-model",
        ollama_base_url="http://127.0.0.1:11434",
        is_space=True,
    )
    with pytest.raises(ValueError, match="只允許 Gemini"):
        blocked.validate()


def test_env_example_has_model_names_but_no_secret_values() -> None:
    env_example = (Path(__file__).parents[1] / ".env.example").read_text(encoding="utf-8")
    assert "GEMINI_MODEL=" in env_example
    assert "OLLAMA_F1_MODEL=" in env_example
    assert "OLLAMA_BASELINE_MODEL=" in env_example
    assert "GOOGLE_API_KEY=" in env_example


def test_model_names_have_no_python_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    for name in ("GEMINI_MODEL", "OLLAMA_F1_MODEL", "OLLAMA_BASELINE_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("GEMINI_MODEL", "cloud-model-from-environment")

    cloud = AgentSettings.from_env(
        provider=AgentProvider.GEMINI,
        dotenv_path=tmp_path / "does-not-exist",
    )
    assert cloud.selected_model == "cloud-model-from-environment"
    assert cloud.ollama_f1_model == ""

    with pytest.raises(ValueError, match="OLLAMA_BASELINE_MODEL"):
        AgentSettings.from_env(
            provider=AgentProvider.GEMMA3_BASELINE,
            dotenv_path=tmp_path / "does-not-exist",
        )

    config_source = (
        Path(__file__).parents[1]
        / "src"
        / "ltc_benefit_agent"
        / "agent"
        / "config.py"
    ).read_text(encoding="utf-8")
    assert "gemini-3.1-flash-lite" not in config_source
    assert "ltc-f1:q4_k_m" not in config_source
    assert "ltc-gemma3-tools:12b" not in config_source


def test_local_timeout_is_validated() -> None:
    invalid = AgentSettings(
        provider=AgentProvider.F1_OLLAMA,
        gemini_model="",
        ollama_f1_model="local-model",
        ollama_baseline_model="",
        ollama_base_url="http://127.0.0.1:11434",
        is_space=False,
        ollama_timeout_seconds=0,
    )
    with pytest.raises(ValueError, match="必須大於 0"):
        invalid.validate()


def test_local_timeout_is_forwarded_to_model_client() -> None:
    settings = AgentSettings(
        provider=AgentProvider.F1_OLLAMA,
        gemini_model="",
        ollama_f1_model="local-model",
        ollama_baseline_model="",
        ollama_base_url="http://127.0.0.1:11434",
        is_space=False,
        ollama_timeout_seconds=12.5,
    )
    model = build_chat_model(settings)
    assert model.sync_client_kwargs == {"timeout": 12.5}
