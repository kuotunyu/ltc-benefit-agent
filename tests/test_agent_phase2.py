from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Sequence

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import BaseTool
from pydantic import Field

from ltc_benefit_agent.agent.config import AgentProvider, AgentSettings
from ltc_benefit_agent.agent.factory import build_agent_runtime, build_chat_model
from ltc_benefit_agent.agent.intake import (
    explicit_cms_intent,
    merge_explicit_case_facts,
)
from ltc_benefit_agent.agent.privacy import SafeAuditLogger, redact_text
from ltc_benefit_agent.agent.reports import (
    ReportPublicationRejected,
    ReportRegistry,
    render_report,
)
from ltc_benefit_agent.agent.service import AgentTurnResult, BenefitAgentService
from ltc_benefit_agent.agent.toolset import build_tool_bundle
from ltc_benefit_agent.agent.workflow import (
    CURRENT_WITH_HISTORICAL_COMPARISON_DIRECTIVE,
    _explicit_compare_legacy,
)
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

COMPLETE_REPORT_USER_TEXT = (
    "家人 70 歲，不是原住民，沒有身障證明、沒有失智診斷，也不是 PAC；"
    "生活需要協助已 12 個月，住家裡。正式 CMS 2，第三類，沒有外籍看護，"
    "預計每月服務費 20000 元。"
)

UNKNOWN_CMS_PUBLIC_USER_TEXT = (
    "家人 70 歲，住在家裡。洗澡和穿衣需要他人協助，已持續 8 個月；"
    "吃飯、起身走動和如廁不需要協助。不是原住民，沒有身心障礙證明，"
    "沒有確診失智，也不是 PAC 個案。目前尚未接受正式 CMS 評估，"
    "不知道 CMS 等級。請不要推估 CMS，只提供資格初篩、CMS 2 至 8 級"
    "參考表與申請方式。"
)


class ScriptedBenefitModel(BaseChatModel):
    """不含自然語言推理，只用來驗證 LangGraph tool/HITL wiring。"""

    seen_batches: list[tuple[BaseMessage, ...]] = Field(default_factory=list)
    bound_tool_names: list[str] = Field(default_factory=list)
    escape_publish_markdown: bool = False
    copay_welfare_category: str = "THIRD"

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
            args["welfare_category"] = self.copay_welfare_category
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
            report_markdown = draft["markdown"]
            if self.escape_publish_markdown:
                report_markdown = report_markdown.replace("\n", "\\n")
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "publish_report",
                        "args": {
                            "report_id": draft["report_id"],
                            "report_markdown": report_markdown,
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


class InitialEligibilityRetryModel(BaseChatModel):
    """第一次只回文字；收到有界 retry prompt 後才由模型產生 tool call。"""

    call_count: int = 0
    saw_retry_prompt: bool = False
    bound_tool_batches: list[tuple[str, ...]] = Field(default_factory=list)
    tool_choices: list[Any] = Field(default_factory=list)
    retry_human_messages: list[str] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "initial-eligibility-retry-test-model"

    def bind_tools(
        self, tools: Sequence[BaseTool | dict[str, Any]], **kwargs: Any
    ) -> "InitialEligibilityRetryModel":
        self.bound_tool_batches.append(
            tuple(
                tool.name if isinstance(tool, BaseTool) else str(tool.get("name"))
                for tool in tools
            )
        )
        self.tool_choices.append(kwargs.get("tool_choice"))
        return self

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        del stop, run_manager, kwargs
        self.call_count += 1
        system_text = "\n".join(
            str(message.content)
            for message in messages
            if isinstance(message, SystemMessage)
        )
        last = messages[-1]
        if isinstance(last, HumanMessage) and "INITIAL_ELIGIBILITY_TOOL_RETRY" in system_text:
            self.saw_retry_prompt = True
            self.retry_human_messages.append(str(last.content))
            message = AIMessage(
                content=(
                    "```tool_call\n"
                    '{"name":"eligibility_check","arguments":{'
                    '"age":49,"indigenous":false,'
                    '"has_disability_certificate":false,'
                    '"has_dementia_diagnosis":false,"is_pac_case":false,'
                    '"has_functional_impairment":true,'
                    '"impairment_duration_months":8,'
                    '"residence_status":"COMMUNITY",'
                    '"official_cms_level":null,'
                    '"rule_version":"CURRENT_2026_07"}}\n```'
                )
            )
        elif isinstance(last, HumanMessage):
            message = AIMessage(content="請先補充需要的資格初篩資料。")
        elif isinstance(last, ToolMessage):
            message = AIMessage(content="資格初篩工具已完成。")
        else:  # pragma: no cover - exposes unexpected graph transitions
            raise AssertionError(f"unexpected last message: {last!r}")
        return ChatResult(generations=[ChatGeneration(message=message)])


class PrematureStoppingModel(BaseChatModel):
    """每個工具後都先停住，用來驗證 middleware 能有限度續跑。"""

    seen_system_prompts: list[str] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "premature-stopping-test-model"

    def bind_tools(
        self, tools: Sequence[BaseTool | dict[str, Any]], **kwargs: Any
    ) -> "PrematureStoppingModel":
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
        system_text = "\n".join(
            str(message.content)
            for message in messages
            if isinstance(message, SystemMessage)
        )
        self.seen_system_prompts.append(system_text)
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
                        "id": "guard-call-1",
                    }
                ],
            )
        elif isinstance(last, ToolMessage) and "eligibility_check 已完成" in system_text:
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
                    {
                        "name": "copay_estimate",
                        "args": args,
                        "id": "guard-call-2",
                    }
                ],
            )
        elif isinstance(last, ToolMessage) and "copay_estimate 已成功完成" in system_text:
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "build_report_draft",
                        "args": COMPLETE_REPORT_ARGS,
                        "id": "guard-call-3",
                    }
                ],
            )
        elif isinstance(last, ToolMessage) and "build_report_draft 已成功完成" in system_text:
            draft_message = next(
                message
                for message in reversed(messages)
                if isinstance(message, ToolMessage)
                and message.name == "build_report_draft"
            )
            draft = json.loads(str(draft_message.content))
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "publish_report",
                        "args": {
                            "report_id": draft["report_id"],
                            "report_markdown": draft["markdown"],
                        },
                        "id": "guard-call-4",
                    }
                ],
            )
        elif isinstance(last, ToolMessage):
            message = AIMessage(content=f"已取得 {last.name} 結果，先到這裡。")
        else:  # pragma: no cover - exposes unexpected middleware transitions
            raise AssertionError(f"unexpected last message: {last!r}")
        return ChatResult(generations=[ChatGeneration(message=message)])


class InsufficientEligibilityModel(BaseChatModel):
    """資格工具明確回傳缺漏時，middleware 不應逼模型建稿。"""

    call_count: int = 0

    @property
    def _llm_type(self) -> str:
        return "insufficient-eligibility-test-model"

    def bind_tools(
        self, tools: Sequence[BaseTool | dict[str, Any]], **kwargs: Any
    ) -> "InsufficientEligibilityModel":
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
        self.call_count += 1
        last = messages[-1]
        if isinstance(last, HumanMessage):
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "eligibility_check",
                        "args": {
                            "age": 70,
                            "indigenous": False,
                            "has_disability_certificate": False,
                            "has_dementia_diagnosis": False,
                            "is_pac_case": False,
                            "has_functional_impairment": None,
                            "impairment_duration_months": None,
                            "residence_status": "COMMUNITY",
                            "official_cms_level": None,
                            "rule_version": "CURRENT_2026_07",
                        },
                        "id": "missing-call-1",
                    }
                ],
            )
        elif isinstance(last, ToolMessage):
            message = AIMessage(content="請問日常生活是否需要他人協助？")
        else:  # pragma: no cover - middleware 不應在此情境續跑
            raise AssertionError(f"unexpected extra model call: {last!r}")
        return ChatResult(generations=[ChatGeneration(message=message)])


class UnknownCmsStoppingModel(BaseChatModel):
    """未知 CMS 完成初篩後停住，middleware 應直接建參考報告。"""

    @property
    def _llm_type(self) -> str:
        return "unknown-cms-stopping-test-model"

    def bind_tools(
        self, tools: Sequence[BaseTool | dict[str, Any]], **kwargs: Any
    ) -> "UnknownCmsStoppingModel":
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
        last = messages[-1]
        if isinstance(last, HumanMessage):
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "eligibility_check",
                        "args": {
                            "age": 70,
                            "indigenous": False,
                            "has_disability_certificate": False,
                            "has_dementia_diagnosis": False,
                            "is_pac_case": False,
                            "has_functional_impairment": True,
                            "impairment_duration_months": 8,
                            "residence_status": "COMMUNITY",
                            "official_cms_level": None,
                            "rule_version": "CURRENT_2026_07",
                        },
                        "id": "unknown-cms-call-1",
                    }
                ],
            )
        elif isinstance(last, ToolMessage):
            message = AIMessage(content=f"已取得 {last.name}，先到這裡。")
        else:  # pragma: no cover - exposes unexpected middleware transitions
            raise AssertionError(f"unexpected last message: {last!r}")
        return ChatResult(generations=[ChatGeneration(message=message)])


class UnknownCmsGuessingModel(BaseChatModel):
    """刻意把參考範圍猜成 CMS 2，驗證 middleware 會在工具前阻擋。"""

    @property
    def _llm_type(self) -> str:
        return "unknown-cms-guessing-test-model"

    def bind_tools(
        self, tools: Sequence[BaseTool | dict[str, Any]], **kwargs: Any
    ) -> "UnknownCmsGuessingModel":
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
        last = messages[-1]
        if isinstance(last, HumanMessage):
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "eligibility_check",
                        "args": {
                            "age": 70,
                            "indigenous": False,
                            "has_disability_certificate": False,
                            "has_dementia_diagnosis": False,
                            "is_pac_case": False,
                            "has_functional_impairment": True,
                            "impairment_duration_months": 8,
                            "residence_status": "COMMUNITY",
                            "official_cms_level": 2,
                            "rule_version": "CURRENT_2026_07",
                        },
                        "id": "unknown-guess-eligibility",
                    }
                ],
            )
        elif isinstance(last, ToolMessage) and last.name == "eligibility_check":
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "copay_estimate",
                        "args": {
                            "cms_level": 2,
                            "welfare_category": "THIRD",
                            "has_foreign_caregiver": False,
                            "planned_spend": 10_020,
                            "rule_version": "CURRENT_2026_07",
                        },
                        "id": "unknown-guess-copay",
                    }
                ],
            )
        elif isinstance(last, ToolMessage) and last.name == "build_report_draft":
            message = AIMessage(content="草稿已建立。")
        else:  # pragma: no cover - exposes unexpected middleware transitions
            raise AssertionError(f"unexpected last message: {last!r}")
        return ChatResult(generations=[ChatGeneration(message=message)])


class CrossTurnSkippingModel(BaseChatModel):
    """模擬小模型忘記舊欄位，並在第二輪過早跳到金額工具。"""

    @property
    def _llm_type(self) -> str:
        return "cross-turn-skipping-test-model"

    def bind_tools(
        self, tools: Sequence[BaseTool | dict[str, Any]], **kwargs: Any
    ) -> "CrossTurnSkippingModel":
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
        last = messages[-1]
        if isinstance(last, HumanMessage):
            turn_count = sum(isinstance(message, HumanMessage) for message in messages)
            if turn_count == 1:
                message = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "eligibility_check",
                            "args": {"age": 65},
                            "id": "intake-first-eligibility",
                        }
                    ],
                )
            else:
                message = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "copay_estimate",
                            "args": {
                                "cms_level": 2,
                                "welfare_category": "THIRD",
                                "has_foreign_caregiver": False,
                                "planned_spend": 10_000,
                            },
                            "id": "intake-premature-copay",
                        }
                    ],
                )
        elif isinstance(last, ToolMessage) and last.status == "error":
            message = AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "eligibility_check",
                        # 刻意不再傳 age，middleware 必須保留第一輪已知值。
                        "args": {
                            "indigenous": False,
                            "has_disability_certificate": False,
                            "has_dementia_diagnosis": False,
                            "is_pac_case": False,
                            "has_functional_impairment": True,
                            # 刻意誤讀；middleware 必須以明確的「6 個月」校正。
                            "impairment_duration_months": 60,
                            "residence_status": "COMMUNITY",
                            # 刻意漏掉明確的「CMS 2」。
                            "official_cms_level": None,
                        },
                        "id": "intake-second-eligibility",
                    }
                ],
            )
        elif isinstance(last, ToolMessage) and last.name == "eligibility_check":
            payload = json.loads(str(last.content))
            if payload["status"] == "INSUFFICIENT_INFORMATION":
                message = AIMessage(content="")
            else:
                message = AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "copay_estimate",
                            "args": {
                                "cms_level": 2,
                                "welfare_category": "THIRD",
                                "has_foreign_caregiver": False,
                                "planned_spend": 10_000,
                            },
                            "id": "intake-valid-copay",
                        }
                    ],
                )
        elif isinstance(last, ToolMessage) and last.name == "copay_estimate":
            message = AIMessage(content="")
        elif isinstance(last, ToolMessage) and last.name == "build_report_draft":
            message = AIMessage(content="")
        else:  # pragma: no cover - exposes unexpected graph transitions
            raise AssertionError(f"unexpected last message: {last!r}")
        return ChatResult(generations=[ChatGeneration(message=message)])


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
    assert "尚未經工具驗證" in unsafe.latest_text

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


def test_latest_text_reads_langchain_standard_content_blocks() -> None:
    result = AgentTurnResult(
        "thread-content-blocks",
        {
            "messages": [
                AIMessage(
                    content=[
                        {"type": "reasoning", "reasoning": "internal"},
                        {
                            "type": "text",
                            "text": "收到，請問日常生活需要哪些協助？",
                        },
                    ]
                )
            ]
        },
        (),
    )

    assert result.latest_text == "收到，請問日常生活需要哪些協助？"


def test_full_create_agent_flow_masks_pii_and_waits_for_exact_approval() -> None:
    model = ScriptedBenefitModel()
    audit = SafeAuditLogger()
    runtime = build_agent_runtime(settings=settings(), model=model, audit=audit)
    service = BenefitAgentService(runtime)

    pii = "我叫王小明，A123456789，電話 0912-345-678。" + COMPLETE_REPORT_USER_TEXT
    pending = service.send_message("thread-a", pii)

    assert pending.awaiting_approval
    preview = pending.pending_report_preview
    assert preview is not None, repr(pending.interrupts)
    assert preview.startswith("# 長照服務資格與補助初步建議書")
    assert pending.latest_text == (
        "補助試算報告草稿已產生，請檢查資格與金額後決定是否核准。"
    )
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

    repeated = service.decide("thread-a", "approve")
    assert not repeated.awaiting_approval
    assert repeated.latest_text == preview

    log_text = repr(audit.snapshot())
    for secret in ("王小明", "A123456789", "0912-345-678"):
        assert secret not in log_text
    assert "tool_call" in log_text
    assert "tool_result" in log_text
    assert "human_decision" in log_text
    assert log_text.count("human_decision") == 1


def test_publish_call_uses_exact_draft_when_adapter_reescapes_newlines() -> None:
    model = ScriptedBenefitModel(escape_publish_markdown=True)
    service = BenefitAgentService(
        build_agent_runtime(settings=settings(), model=model)
    )

    pending = service.send_message("thread-reescaped-publish", COMPLETE_REPORT_USER_TEXT)

    assert pending.awaiting_approval
    preview = pending.pending_report_preview
    assert preview is not None
    assert "\n## 資格初篩" in preview
    assert "\\n## 資格初篩" not in preview
    approved = service.decide("thread-reescaped-publish", "approve")
    assert approved.latest_text == preview


def test_workflow_guard_continues_three_stalled_stages_until_hitl() -> None:
    model = PrematureStoppingModel()
    service = BenefitAgentService(
        build_agent_runtime(settings=settings(), model=model)
    )

    pending = service.send_message("thread-workflow-guard", COMPLETE_REPORT_USER_TEXT)

    assert pending.awaiting_approval
    assert pending.pending_report_preview is not None
    assert "NT$ 11,583" in pending.pending_report_preview
    assert pending.state["workflow_guard_nudge_count"] == 3
    prompts = "\n".join(model.seen_system_prompts)
    assert "eligibility_check 已完成" in prompts
    tool_messages = [
        message.name
        for message in pending.state["messages"]
        if isinstance(message, ToolMessage)
    ]
    assert tool_messages == [
        "eligibility_check",
        "copay_estimate",
        "build_report_draft",
    ]


def test_workflow_guard_builds_reference_report_without_guessing_unknown_cms() -> None:
    service = BenefitAgentService(
        build_agent_runtime(settings=settings(), model=UnknownCmsStoppingModel())
    )

    pending = service.send_message(
        "thread-unknown-cms-guard",
        "家人 70 歲，不是原住民，沒有身障或失智，也不是 PAC；"
        "生活需要協助已 8 個月，住家裡，尚未做 CMS 評估。",
    )

    assert pending.awaiting_approval
    preview = pending.pending_report_preview
    assert preview is not None
    assert "CMS 未知：僅提供額度參考" in preview
    assert "CMS 是照管中心評估後核定的長照需要等級" in preview
    assert "不做個人化試算，也不從描述猜級" in preview
    assert "| 8 | NT$ 36,180 | NT$ 10,854 |" in preview
    assert "政府給付" not in preview
    assert "CMS（照管中心核定的長照需要等級）" in pending.latest_text
    assert "1966" in pending.latest_text
    assert pending.state["workflow_guard_nudge_count"] == 2


def test_public_unknown_cms_wording_cannot_be_guessed_as_level_two() -> None:
    service = BenefitAgentService(
        build_agent_runtime(settings=settings(), model=UnknownCmsGuessingModel())
    )

    pending = service.send_message(
        "thread-public-unknown-cms-regression",
        UNKNOWN_CMS_PUBLIC_USER_TEXT,
    )

    assert pending.awaiting_approval
    preview = pending.pending_report_preview
    assert preview is not None
    assert "CMS 未知：僅提供額度參考" in preview
    assert "不做個人化試算，也不從描述猜級" in preview
    assert "| 2 | NT$ 10,020 | NT$ 3,006 |" in preview
    assert "| 8 | NT$ 36,180 | NT$ 10,854 |" in preview
    assert "政府給付" not in preview
    assert "合計自付" not in preview
    successful_tools = [
        message
        for message in pending.state["messages"]
        if isinstance(message, ToolMessage)
        and getattr(message, "status", "success") != "error"
    ]
    assert [message.name for message in successful_tools] == [
        "eligibility_check",
        "build_report_draft",
    ]
    eligibility_args = successful_tools[0].artifact["validated_arguments"]
    assert eligibility_args["official_cms_level"] is None
    assert eligibility_args["has_functional_impairment"] is True
    assert pending.state["case_explicit_eligibility_facts"][
        "official_cms_level"
    ] is None
    assert pending.state["case_explicit_copay_facts"]["cms_level"] is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("正式 CMS 4。", (True, 4)),
        ("CMS 2 至 8 級參考表", (False, None)),
        ("CMS 2–8 級參考表", (False, None)),
        ("尚未接受正式 CMS 評估，不知道 CMS 等級。", (True, None)),
    ],
)
def test_explicit_cms_intent_distinguishes_level_unknown_and_reference_range(
    text: str, expected: tuple[bool, int | None]
) -> None:
    assert explicit_cms_intent([HumanMessage(content=text)]) == expected


def test_latest_explicit_cms_intent_overrides_earlier_turn() -> None:
    assert explicit_cms_intent(
        [
            HumanMessage(content="目前不知道 CMS 等級。"),
            HumanMessage(content="後來查到正式 CMS 4。"),
        ]
    ) == (True, 4)
    assert explicit_cms_intent(
        [
            HumanMessage(content="先前以為正式 CMS 4。"),
            HumanMessage(content="前述有誤，CMS 尚未評估。"),
        ]
    ) == (True, None)


def test_intake_guard_returns_deterministic_missing_information_followup() -> None:
    model = InsufficientEligibilityModel()
    service = BenefitAgentService(
        build_agent_runtime(settings=settings(), model=model)
    )

    result = service.send_message("thread-missing-information", "家人 70 歲")

    assert not result.awaiting_approval
    assert "需要他人協助" in result.latest_text
    assert "住家裡" in result.latest_text
    assert "正式 CMS" in result.latest_text
    assert "長照需要等級" in result.latest_text
    assert "尚未評估可直接說不知道" in result.latest_text
    assert result.state["workflow_guard_nudge_count"] == 0
    assert model.call_count == 2


def test_intake_guard_reprompts_model_once_for_missing_initial_tool_call() -> None:
    model = InitialEligibilityRetryModel()
    audit = SafeAuditLogger()
    service = BenefitAgentService(
        build_agent_runtime(settings=settings(), model=model, audit=audit)
    )

    result = service.send_message(
        "thread-initial-tool-retry",
        "家人 49 歲，不是原住民，沒有身障或失智，也不是 PAC；"
        "生活需要協助已 8 個月，住家裡，尚未做 CMS 評估。",
    )

    eligibility_calls = [
        event
        for event in audit.snapshot()
        if event.event == "tool_call" and event.tool_name == "eligibility_check"
    ]
    assert model.saw_retry_prompt
    assert model.call_count >= 2
    assert ("eligibility_check",) in model.bound_tool_batches
    retry_index = model.bound_tool_batches.index(("eligibility_check",))
    assert model.tool_choices[retry_index] == "eligibility_check"
    assert model.retry_human_messages == [
        "請依 system 提供的結構化欄位，立即呼叫唯一的 eligibility_check 工具；"
        "不要輸出其他文字。"
    ]
    assert len(eligibility_calls) == 1
    assert eligibility_calls[0].payload["age"] == 49
    assert eligibility_calls[0].payload["has_dementia_diagnosis"] is False
    assert eligibility_calls[0].payload["impairment_duration_months"] == 8
    assert result.awaiting_approval
    assert result.pending_report_preview is not None
    assert "結論：初步未符合規則" in result.pending_report_preview
    assert "PRELIMINARY_CRITERIA_NOT_MET" not in result.pending_report_preview


def test_intake_guard_does_not_force_initial_tool_for_single_fact() -> None:
    model = InitialEligibilityRetryModel()
    audit = SafeAuditLogger()
    service = BenefitAgentService(
        build_agent_runtime(settings=settings(), model=model, audit=audit)
    )

    result = service.send_message("thread-no-initial-tool-retry", "家人 49 歲")

    assert not model.saw_retry_prompt
    assert model.call_count == 1
    assert result.latest_text == "請先補充需要的資格初篩資料。"
    assert not any(
        event.event == "tool_call" and event.tool_name == "eligibility_check"
        for event in audit.snapshot()
    )


def test_intake_guard_keeps_cross_turn_facts_and_blocks_premature_copay() -> None:
    audit = SafeAuditLogger()
    service = BenefitAgentService(
        build_agent_runtime(
            settings=settings(), model=CrossTurnSkippingModel(), audit=audit
        )
    )

    first = service.send_message("thread-intake-guard", "家人剛滿 65 歲，能試算嗎？")

    assert not first.awaiting_approval
    assert "需要協助" in first.latest_text
    assert "正式 CMS" in first.latest_text

    pending = service.send_message(
        "thread-intake-guard",
        "不是原住民、沒有身障或失智、不是 PAC；失能 6 個月，住家裡。"
        "正式 CMS 2，第三類，沒有外籍看護，預計每月服務費 10000 元。",
    )

    assert pending.awaiting_approval
    assert pending.pending_report_preview is not None
    assert "NT$ 8,400" in pending.pending_report_preview
    assert pending.state["case_explicit_eligibility_facts"] == {
        "age": 65,
        "indigenous": False,
        "has_disability_certificate": False,
        "has_dementia_diagnosis": False,
        "is_pac_case": False,
        "has_functional_impairment": True,
        "impairment_duration_months": 6,
        "residence_status": "COMMUNITY",
        "official_cms_level": 2,
        "rule_version": "CURRENT_2026_07",
    }
    assert pending.state["case_explicit_copay_facts"] == {
        "cms_level": 2,
        "welfare_category": "THIRD",
        "has_foreign_caregiver": False,
        "planned_spend": 10_000,
        "rule_version": "CURRENT_2026_07",
    }
    calls = [
        event
        for event in audit.snapshot()
        if event.event == "tool_call" and event.tool_name is not None
    ]
    eligibility_calls = [
        event.payload for event in calls if event.tool_name == "eligibility_check"
    ]
    assert len(eligibility_calls) == 2
    assert eligibility_calls[-1]["age"] == 65
    assert eligibility_calls[-1]["official_cms_level"] == 2
    assert eligibility_calls[-1]["impairment_duration_months"] == 6
    assert eligibility_calls[-1]["residence_status"] == "COMMUNITY"
    assert [event.tool_name for event in calls] == [
        "eligibility_check",
        "eligibility_check",
        "copay_estimate",
        "build_report_draft",
    ]


def test_reject_does_not_publish_report() -> None:
    model = ScriptedBenefitModel()
    audit = SafeAuditLogger()
    service = BenefitAgentService(
        build_agent_runtime(settings=settings(), model=model, audit=audit)
    )
    pending = service.send_message("thread-reject", COMPLETE_REPORT_USER_TEXT)
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
    assert "CMS 是照管中心評估後核定的長照需要等級" in report
    assert "不做個人化試算" in report
    assert "| 8 | NT$ 36,180 | NT$ 10,854 |" in report
    assert "居家照顧服務以外之照顧組合" in report
    assert "不判定個別服務碼是否適用" in report
    assert "政府給付" not in report
    assert "合計自付" not in report


def test_foreign_caregiver_report_states_service_combination_restriction() -> None:
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
            official_cms_level=2,
            rule_version=RuleVersion.CURRENT_2026_07,
        ),
        welfare_category=WelfareCategory.THIRD,
        has_foreign_caregiver=True,
        planned_spend=3_006,
    )
    assert "外籍家庭看護額度提醒" in report
    assert "居家照顧服務以外之照顧組合" in report
    assert "不判定個別服務碼是否適用" in report


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
    assert "完整快照基準：2026-07-01" in report
    assert "2025-09-01" in report
    assert "2026-01-01" in report
    assert "不代表所有規則都在該日才生效" in report
    assert "生效基準：" not in report
    assert "## 舊制比較" in report
    assert "`LEGACY_2022` 初篩：初步未符合規則" in report


def test_interface_comparison_keeps_current_as_primary_rule() -> None:
    text = (
        "家人 70 歲，已有正式 CMS 第 4 級。\n\n"
        f"{CURRENT_WITH_HISTORICAL_COMPARISON_DIRECTIVE}"
    )

    eligibility, copay = merge_explicit_case_facts(text)

    assert eligibility["rule_version"] == "CURRENT_2026_07"
    assert copay["rule_version"] == "CURRENT_2026_07"
    assert _explicit_compare_legacy([HumanMessage(content=text)])


def test_report_uses_human_readable_eligibility_labels() -> None:
    report = render_report(
        eligibility_input=EligibilityInput(
            age=70,
            indigenous=False,
            has_disability_certificate=False,
            has_dementia_diagnosis=False,
            is_pac_case=False,
            has_functional_impairment=True,
            impairment_duration_months=8,
            residence_status=ResidenceStatus.COMMUNITY,
            official_cms_level=4,
            rule_version=RuleVersion.CURRENT_2026_07,
        ),
        welfare_category=WelfareCategory.THIRD,
        has_foreign_caregiver=False,
        planned_spend=18_000,
    )

    assert "結論：已提供正式 CMS，可進行參考試算" in report
    assert "符合身分依據：65 歲以上老人" in report
    assert "CMS_PROVIDED_FOR_ESTIMATE" not in report
    assert "AGE_65_OR_OVER" not in report


@pytest.mark.parametrize(
    ("user_label", "expected"),
    [
        ("第一類", "FIRST"),
        ("長照低收入戶", "FIRST"),
        ("第二類", "SECOND"),
        ("長照中低收入戶", "SECOND"),
        ("第三類", "THIRD"),
        ("長照一般戶", "THIRD"),
        ("一般戶", "THIRD"),
    ],
)
def test_intake_normalizes_welfare_category_labels(
    user_label: str, expected: str
) -> None:
    _, copay = merge_explicit_case_facts(f"福利身分是{user_label}")

    assert copay["welfare_category"] == expected


def test_explicit_general_household_overrides_wrong_model_category() -> None:
    model = ScriptedBenefitModel(copay_welfare_category="FIRST")
    audit = SafeAuditLogger()
    service = BenefitAgentService(
        build_agent_runtime(settings=settings(), model=model, audit=audit)
    )

    pending = service.send_message(
        "thread-general-household",
        "家人 75 歲，不是原住民，沒有身障證明、失智或 PAC；"
        "需要協助已 8 個月，住家裡。正式 CMS 4，屬一般戶，"
        "沒有外籍看護，預計服務費 18000 元。",
    )

    assert pending.awaiting_approval
    assert pending.pending_report_preview is not None
    assert "| 法定福利類別 | 第三類 |" in pending.pending_report_preview
    assert "| 部分負擔比率 | 16% |" in pending.pending_report_preview
    assert "| 政府給付 | NT$ 15,120 |" in pending.pending_report_preview
    assert "| 額度內部分負擔 | NT$ 2,880 |" in pending.pending_report_preview
    copay_calls = [
        event.payload
        for event in audit.snapshot()
        if event.event == "tool_call" and event.tool_name == "copay_estimate"
    ]
    assert copay_calls[-1]["welfare_category"] == "THIRD"


def test_tools_reject_invalid_money_arguments_without_llm_math() -> None:
    tools = {item.name: item for item in build_tool_bundle().tools}
    eligibility_schema = tools["eligibility_check"].args_schema.model_json_schema()
    assert "COMMUNITY" in eligibility_schema["properties"]["residence_status"][
        "description"
    ]
    assert "false" in eligibility_schema["properties"]["is_pac_case"]["description"]
    assert not {
        "age",
        "indigenous",
        "has_disability_certificate",
        "has_dementia_diagnosis",
        "is_pac_case",
        "has_functional_impairment",
        "impairment_duration_months",
        "residence_status",
    }.intersection(eligibility_schema.get("required", []))
    conservative = json.loads(
        tools["eligibility_check"].invoke(
            {
                "age": 70,
                "indigenous": False,
                "has_disability_certificate": False,
                "has_dementia_diagnosis": False,
                "is_pac_case": False,
                "residence_status": "COMMUNITY",
                "official_cms_level": 4,
            }
        )
    )
    assert conservative["status"] == "CMS_PROVIDED_FOR_ESTIMATE"
    assert conservative["official_cms_level"] == 4
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


def test_gemini_35_omits_sampling_params_and_uses_configured_thinking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    sentinel = object()

    def fake_init_chat_model(model: str, **kwargs: Any) -> object:
        captured["model"] = model
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(
        "ltc_benefit_agent.agent.factory.init_chat_model", fake_init_chat_model
    )
    cloud = AgentSettings(
        provider=AgentProvider.GEMINI,
        gemini_model="cloud-model-from-environment",
        ollama_f1_model="",
        ollama_baseline_model="",
        ollama_base_url="http://127.0.0.1:11434",
        is_space=False,
        gemini_thinking_level="medium",
    )

    assert build_chat_model(cloud) is sentinel
    assert captured["model"] == "cloud-model-from-environment"
    assert captured["model_provider"] == "google_genai"
    assert captured["thinking_level"] == "medium"
    for deprecated in ("temperature", "top_p", "top_k", "candidate_count"):
        assert deprecated not in captured


def test_gemini_thinking_level_is_validated() -> None:
    invalid = AgentSettings(
        provider=AgentProvider.GEMINI,
        gemini_model="cloud-model",
        ollama_f1_model="",
        ollama_baseline_model="",
        ollama_base_url="http://127.0.0.1:11434",
        is_space=False,
        gemini_thinking_level="extreme",  # type: ignore[arg-type]
    )
    with pytest.raises(ValueError, match="GEMINI_THINKING_LEVEL"):
        invalid.validate()
