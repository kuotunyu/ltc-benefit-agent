"""在模型提早停止時，有限度地推動既定報告流程。

本 middleware 不解析使用者敘述、不補參數，也不判斷資格或金額。它只根據
同一輪中已成功完成的確定性工具，提醒模型執行下一個既定步驟。
"""

from __future__ import annotations

import json
import re
from enum import StrEnum
from typing import Any, NotRequired
from uuid import uuid4

from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRequest,
    hook_config,
)
from langchain.agents.middleware.types import AgentState
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage


class WorkflowGuardState(AgentState):
    """只在單次 agent invocation 內使用的流程保護狀態。"""

    workflow_guard_nudge_count: NotRequired[int]
    workflow_guard_last_stage: NotRequired[str]
    workflow_guard_prompt: NotRequired[str | None]


class _WorkflowStage(StrEnum):
    ELIGIBILITY_RECHECK = "ELIGIBILITY_RECHECK"
    ELIGIBILITY_READY = "ELIGIBILITY_READY"
    COPAY_READY = "COPAY_READY"
    DRAFT_READY = "DRAFT_READY"


_MAX_NUDGES_PER_INVOCATION = 3

# UI 只用此指令表示「現制主報告另附歷史快照比較」。字串刻意不含
# LEGACY_2022／2022／舊制，避免 intake 將比較意圖誤判為切換主規則版本。
CURRENT_WITH_HISTORICAL_COMPARISON_DIRECTIVE = (
    "[INTERFACE_COMPARE_HISTORICAL_SNAPSHOT=true; "
    "PRIMARY_RULE=CURRENT_2026_07]"
)

_EXPLICIT_CMS_PATTERN = re.compile(
    r"(?<![A-Za-z])CMS\s*(?:等級)?\s*[:：]?\s*[2-8](?!\d)", re.IGNORECASE
)

_STAGE_PROMPTS = {
    _WorkflowStage.COPAY_READY: (
        "流程續跑檢查：copay_estimate 已成功完成。請立即依原對話中的資料呼叫 "
        "build_report_draft；不得自行重算、改寫或補造任何資格與金額。"
    ),
    _WorkflowStage.DRAFT_READY: (
        "流程續跑檢查：build_report_draft 已成功完成。現在只能使用該工具結果中的 "
        "report_id 與 markdown 原文呼叫 publish_report；不得改寫草稿，也不要先輸出解說。"
    ),
}


def _message_text(message: BaseMessage) -> str:
    if isinstance(message.content, str):
        return message.content
    parts: list[str] = []
    for block in message.content_blocks:
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
    return "".join(parts)


def _current_turn(messages: list[BaseMessage]) -> list[BaseMessage]:
    for index in range(len(messages) - 1, -1, -1):
        if isinstance(messages[index], HumanMessage):
            return messages[index + 1 :]
    return messages


def _successful_tool_messages(messages: list[BaseMessage]) -> list[ToolMessage]:
    return [
        message
        for message in _current_turn(messages)
        if isinstance(message, ToolMessage)
        and getattr(message, "status", "success") != "error"
    ]


def _eligibility_payload(message: ToolMessage) -> dict[str, Any] | None:
    if not isinstance(message.content, str):
        return None
    try:
        payload = json.loads(message.content)
    except (TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _latest_tool_call_args(
    messages: list[BaseMessage], tool_name: str
) -> dict[str, Any] | None:
    for message in reversed(_current_turn(messages)):
        if not isinstance(message, ToolMessage) or message.name != tool_name:
            continue
        artifact = message.artifact
        if not isinstance(artifact, dict):
            continue
        args = artifact.get("validated_arguments")
        if isinstance(args, dict):
            return dict(args)
    for message in reversed(_current_turn(messages)):
        if not isinstance(message, AIMessage):
            continue
        for tool_call in reversed(message.tool_calls):
            if tool_call.get("name") != tool_name:
                continue
            args = tool_call.get("args")
            return dict(args) if isinstance(args, dict) else None
    return None


def _latest_tool_message(
    messages: list[BaseMessage], tool_name: str
) -> ToolMessage | None:
    for message in reversed(_current_turn(messages)):
        if (
            isinstance(message, ToolMessage)
            and message.name == tool_name
            and getattr(message, "status", "success") != "error"
        ):
            return message
    return None


def _explicit_compare_legacy(messages: list[BaseMessage]) -> bool:
    for message in reversed(messages):
        if not isinstance(message, HumanMessage):
            continue
        text = _message_text(message)
        return (
            CURRENT_WITH_HISTORICAL_COMPARISON_DIRECTIVE in text
            or "LEGACY_2022" in text
            or (
                "2022" in text
                and any(keyword in text for keyword in ("比較", "並列"))
            )
        )
    return False


def _human_provided_explicit_cms(messages: list[BaseMessage]) -> bool:
    return any(
        isinstance(message, HumanMessage)
        and _EXPLICIT_CMS_PATTERN.search(_message_text(message))
        for message in messages
    )


def _build_report_tool_call(
    messages: list[BaseMessage], *, require_copay: bool
) -> dict[str, Any] | None:
    eligibility_args = _latest_tool_call_args(messages, "eligibility_check")
    eligibility_message = _latest_tool_message(messages, "eligibility_check")
    if eligibility_args is None or eligibility_message is None:
        return None
    eligibility_result = _eligibility_payload(eligibility_message)
    if eligibility_result is None:
        return None

    copay_args = _latest_tool_call_args(messages, "copay_estimate")
    if require_copay and copay_args is None:
        return None
    copay_args = copay_args or {}
    report_args = {
        "age": eligibility_args.get("age"),
        "indigenous": eligibility_args.get("indigenous"),
        "has_disability_certificate": eligibility_args.get(
            "has_disability_certificate"
        ),
        "has_dementia_diagnosis": eligibility_args.get("has_dementia_diagnosis"),
        "is_pac_case": eligibility_args.get("is_pac_case"),
        "has_functional_impairment": eligibility_args.get(
            "has_functional_impairment"
        ),
        "impairment_duration_months": eligibility_args.get(
            "impairment_duration_months"
        ),
        "residence_status": eligibility_args.get("residence_status", "UNKNOWN"),
        "official_cms_level": eligibility_result.get("official_cms_level"),
        "welfare_category": copay_args.get("welfare_category"),
        "has_foreign_caregiver": copay_args.get("has_foreign_caregiver"),
        "planned_spend": copay_args.get("planned_spend"),
        "rule_version": copay_args.get(
            "rule_version",
            eligibility_args.get("rule_version", "CURRENT_2026_07"),
        ),
        "compare_legacy": _explicit_compare_legacy(messages),
    }
    return {
        "name": "build_report_draft",
        "args": report_args,
        "id": f"workflow-build-{uuid4().hex}",
    }


def _publish_report_tool_call(messages: list[BaseMessage]) -> dict[str, Any] | None:
    draft_message = _latest_tool_message(messages, "build_report_draft")
    if draft_message is None or not isinstance(draft_message.content, str):
        return None
    try:
        draft = json.loads(draft_message.content)
    except json.JSONDecodeError:
        return None
    report_id = draft.get("report_id") if isinstance(draft, dict) else None
    markdown = draft.get("markdown") if isinstance(draft, dict) else None
    if not isinstance(report_id, str) or not isinstance(markdown, str):
        return None
    return {
        "name": "publish_report",
        "args": {"report_id": report_id, "report_markdown": markdown},
        "id": f"workflow-publish-{uuid4().hex}",
    }


def _deterministic_continuation(
    messages: list[BaseMessage], stage: _WorkflowStage
) -> dict[str, Any] | None:
    if stage is _WorkflowStage.DRAFT_READY:
        return _publish_report_tool_call(messages)
    if stage is _WorkflowStage.COPAY_READY:
        return _build_report_tool_call(messages, require_copay=True)
    if stage is _WorkflowStage.ELIGIBILITY_READY:
        eligibility_message = _latest_tool_message(messages, "eligibility_check")
        if eligibility_message is None:
            return None
        eligibility_result = _eligibility_payload(eligibility_message)
        if eligibility_result is not None and eligibility_result.get(
            "official_cms_level"
        ) is None:
            return _build_report_tool_call(messages, require_copay=False)
    return None


def _next_stage(
    messages: list[BaseMessage], latest_response: AIMessage
) -> tuple[_WorkflowStage, str] | None:
    successful = _successful_tool_messages(messages)
    response_text = _message_text(latest_response)
    if any(message.name == "publish_report" for message in successful):
        return None
    if "rejected the tool call for `publish_report`" in response_text:
        return None
    for message in reversed(successful):
        if message.name == "build_report_draft":
            return _WorkflowStage.DRAFT_READY, _STAGE_PROMPTS[_WorkflowStage.DRAFT_READY]
        if message.name == "copay_estimate":
            return _WorkflowStage.COPAY_READY, _STAGE_PROMPTS[_WorkflowStage.COPAY_READY]
        if message.name != "eligibility_check":
            continue

        payload = _eligibility_payload(message)
        if payload is None or payload.get("status") == "INSUFFICIENT_INFORMATION":
            return None

        official_cms_level = payload.get("official_cms_level")
        if official_cms_level is None:
            if _human_provided_explicit_cms(messages):
                return (
                    _WorkflowStage.ELIGIBILITY_RECHECK,
                    "資料一致性檢查：使用者訊息已明確提供正式 CMS 2–8，但剛才的 "
                    "eligibility_check 漏傳 official_cms_level。請先依原文重新呼叫 "
                    "eligibility_check，並保留所有已知欄位；不得建立 CMS 未知報告。",
                )
            return (
                _WorkflowStage.ELIGIBILITY_READY,
                "流程續跑檢查：eligibility_check 已完成，但沒有正式 CMS。請立即呼叫 "
                "build_report_draft，保留 official_cms_level=null，只提供 CMS 2–8 參考表與申請指引；"
                "不得推測 CMS 或試算個人金額。",
            )

        # 已知 CMS 時，福利類別、外籍看護或預計服務費仍可能真的缺漏。
        # 模型若正在追問就不介入；若只是提早收尾，才要求它繼續判斷下一步。
        if "?" in response_text or "？" in response_text:
            return None
        return (
            _WorkflowStage.ELIGIBILITY_READY,
            "流程續跑檢查：eligibility_check 已完成且有正式 CMS。若福利類別、外籍看護與預計服務費"
            "已由使用者提供，請呼叫 copay_estimate；若仍缺資料，只追問缺漏欄位。不要自行假設，也不要"
            "在報告流程完成前提早下結論。",
        )
    return None


class WorkflowContinuationMiddleware(AgentMiddleware):
    """對每個已完成階段最多提醒一次，避免模型停在報告流程中途。"""

    state_schema = WorkflowGuardState

    def before_agent(
        self, state: WorkflowGuardState, runtime: Any
    ) -> dict[str, Any] | None:
        del state, runtime
        return {
            "workflow_guard_nudge_count": 0,
            "workflow_guard_last_stage": "",
            "workflow_guard_prompt": None,
        }

    def wrap_model_call(self, request: ModelRequest, handler: Any) -> Any:
        prompt = request.state.get("workflow_guard_prompt")
        messages = request.messages
        latest = messages[-1] if messages else None
        if (
            not isinstance(prompt, str)
            or not prompt
            or not isinstance(latest, AIMessage)
            or latest.tool_calls
        ):
            return handler(request)

        existing = request.system_message
        base_content = _message_text(existing) if existing is not None else ""
        guarded_system = SystemMessage(
            content=f"{base_content}\n\n{prompt}" if base_content else prompt
        )
        return handler(
            request.override(
                messages=messages[:-1],
                system_message=guarded_system,
            )
        )

    async def awrap_model_call(self, request: ModelRequest, handler: Any) -> Any:
        prompt = request.state.get("workflow_guard_prompt")
        messages = request.messages
        latest = messages[-1] if messages else None
        if (
            not isinstance(prompt, str)
            or not prompt
            or not isinstance(latest, AIMessage)
            or latest.tool_calls
        ):
            return await handler(request)

        existing = request.system_message
        base_content = _message_text(existing) if existing is not None else ""
        guarded_system = SystemMessage(
            content=f"{base_content}\n\n{prompt}" if base_content else prompt
        )
        return await handler(
            request.override(
                messages=messages[:-1],
                system_message=guarded_system,
            )
        )

    @hook_config(can_jump_to=["model"])
    def after_model(
        self, state: WorkflowGuardState, runtime: Any
    ) -> dict[str, Any] | None:
        del runtime
        messages = state.get("messages", [])
        if not messages:
            return None
        latest = messages[-1]
        if not isinstance(latest, AIMessage) or latest.tool_calls:
            return None

        next_stage = _next_stage(messages, latest)
        if next_stage is None:
            return None
        stage, prompt = next_stage
        count = state.get("workflow_guard_nudge_count", 0)
        if count >= _MAX_NUDGES_PER_INVOCATION:
            return None
        if state.get("workflow_guard_last_stage") == stage.value:
            return None
        deterministic_tool_call = _deterministic_continuation(messages, stage)
        if deterministic_tool_call is not None:
            return {
                "messages": [
                    AIMessage(content="", tool_calls=[deterministic_tool_call])
                ],
                "workflow_guard_nudge_count": count + 1,
                "workflow_guard_last_stage": stage.value,
                "workflow_guard_prompt": None,
            }
        return {
            "workflow_guard_nudge_count": count + 1,
            "workflow_guard_last_stage": stage.value,
            "workflow_guard_prompt": prompt,
            "jump_to": "model",
        }


__all__ = ["WorkflowContinuationMiddleware", "WorkflowGuardState"]
