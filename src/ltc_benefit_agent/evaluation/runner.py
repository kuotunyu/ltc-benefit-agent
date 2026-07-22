"""對同一固定情境集執行 create_agent，輸出可稽核 JSON trace。"""

from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from pydantic import SecretStr
from langchain_core.rate_limiters import BaseRateLimiter, InMemoryRateLimiter

from ltc_benefit_agent.agent.config import AgentProvider, AgentSettings
from ltc_benefit_agent.agent.factory import build_agent_runtime
from ltc_benefit_agent.agent.privacy import redact_text
from ltc_benefit_agent.agent.reports import ReportPublicationRejected
from ltc_benefit_agent.agent.service import BenefitAgentService

from .evaluator import (
    EvaluationMetrics,
    ScenarioTrace,
    ToolTrace,
    evaluate_trace,
)
from .cloud_keys import (
    CloudApiKeySlot,
    is_quota_or_rate_limit_error,
    load_cloud_api_key_slots,
    may_failover_without_repeating_progress,
)
from .scenarios import EvaluationScenario, load_scenarios


# The observed cloud project limit is 15 requests/minute. Keep a 20% margin and
# share one limiter across every scenario so rebuilding the agent cannot burst.
CLOUD_EVAL_REQUESTS_PER_SECOND = 12 / 60
REPORT_REJECTION_ERROR_PREFIX = f"{ReportPublicationRejected.__name__}: "


def _is_expected_scenario_failure(error: str | None) -> bool:
    """辨識應計入模型品質分數、但不代表 batch 基礎設施故障的拒絕。"""

    return bool(error and error.startswith(REPORT_REJECTION_ERROR_PREFIX))


def _collect_tool_traces(events: tuple[Any, ...]) -> tuple[ToolTrace, ...]:
    calls: list[ToolTrace] = []
    pending: dict[str, list[int]] = {}
    for event in events:
        if event.tool_name is None:
            continue
        if event.event == "tool_call":
            calls.append(ToolTrace(event.tool_name, event.payload))
            pending.setdefault(event.tool_name, []).append(len(calls) - 1)
        elif event.event == "tool_result" and pending.get(event.tool_name):
            index = pending[event.tool_name].pop(0)
            old = calls[index]
            result = event.payload if isinstance(event.payload, dict) else {"value": event.payload}
            calls[index] = ToolTrace(old.name, old.arguments, result)
    return tuple(calls)


def run_scenario(
    scenario: EvaluationScenario,
    *,
    settings: AgentSettings,
    cloud_api_key: SecretStr | None = None,
    cloud_rate_limiter: BaseRateLimiter | None = None,
) -> tuple[ScenarioTrace, Any]:
    runtime = build_agent_runtime(
        settings=settings,
        cloud_api_key=cloud_api_key,
        cloud_max_retries=0 if cloud_api_key is not None else None,
        cloud_rate_limiter=cloud_rate_limiter,
    )
    service = BenefitAgentService(runtime)
    outputs: list[str] = []
    pending = None
    error = None
    try:
        for index, user_turn in enumerate(scenario.user_turns):
            result = service.send_message(f"eval-{scenario.scenario_id}", user_turn)
            outputs.append(result.latest_text)
            if result.awaiting_approval:
                pending = result
                if index != len(scenario.user_turns) - 1:
                    break
    except Exception as exc:  # evaluator must record one bad case and continue the suite
        error = f"{type(exc).__name__}: {redact_text(str(exc))}"

    preview = pending.pending_report_preview if pending is not None else None
    final_report = None
    if pending is not None and error is None:
        try:
            approved = service.decide(f"eval-{scenario.scenario_id}", "approve")
            final_report = approved.latest_text
        except Exception as exc:
            error = f"{type(exc).__name__}: {redact_text(str(exc))}"

    events = runtime.audit.snapshot()
    trace = ScenarioTrace(
        turn_outputs=tuple(outputs),
        tools=_collect_tool_traces(events),
        pending_preview=preview,
        final_report=final_report,
        hitl_triggered=pending is not None,
        searchable_text="\n".join(
            [*outputs, preview or "", final_report or "", repr(events)]
        ),
        error=error,
    )
    return trace, evaluate_trace(scenario, trace)


def _run_cloud_scenario_with_failover(
    scenario: EvaluationScenario,
    *,
    settings: AgentSettings,
    slots: tuple[CloudApiKeySlot, ...],
    start_index: int,
    rate_limiter: BaseRateLimiter,
) -> tuple[ScenarioTrace, Any, int, list[dict[str, str]], str | None]:
    attempts: list[dict[str, str]] = []
    for index in range(start_index, len(slots)):
        slot = slots[index]
        trace, evaluation = run_scenario(
            scenario,
            settings=settings,
            cloud_api_key=slot.api_key,
            cloud_rate_limiter=rate_limiter,
        )
        if trace.error is None:
            attempts.append({"key_slot": slot.label, "outcome": "completed"})
            return trace, evaluation, index, attempts, None

        if _is_expected_scenario_failure(trace.error):
            attempts.append(
                {"key_slot": slot.label, "outcome": "scenario_failure"}
            )
            return trace, evaluation, index, attempts, None

        quota_error = is_quota_or_rate_limit_error(trace.error)
        no_progress = may_failover_without_repeating_progress(trace)
        if quota_error and no_progress:
            attempts.append({"key_slot": slot.label, "outcome": "quota_no_progress"})
            if index + 1 < len(slots):
                print(
                    f"EVAL_KEY_FAILOVER {scenario.scenario_id} "
                    f"from={slot.label} to={slots[index + 1].label}",
                    flush=True,
                )
                continue
            return trace, evaluation, index, attempts, "all_key_slots_quota_exhausted"

        outcome = "quota_after_progress" if quota_error else "runtime_error"
        attempts.append({"key_slot": slot.label, "outcome": outcome})
        abort_reason = (
            "quota_after_progress" if quota_error else "cloud_runtime_error"
        )
        return trace, evaluation, index, attempts, abort_reason

    raise RuntimeError("沒有可用的雲端 key slot")


def run_suite(
    *,
    provider: AgentProvider,
    output_path: Path,
    scenario_ids: set[str] | None = None,
    allow_cloud: bool = False,
) -> dict[str, Any]:
    if provider is AgentProvider.GEMINI and not allow_cloud:
        raise PermissionError(
            "雲端評估必須先完成成本確認，再明確傳入 allow_cloud=True"
        )
    settings = AgentSettings.from_env(provider=provider)
    cloud_slots = (
        load_cloud_api_key_slots()
        if provider is AgentProvider.GEMINI
        else ()
    )
    if provider is AgentProvider.GEMINI and not cloud_slots:
        raise ValueError("請在 .env 設定主要雲端 API key")
    cloud_rate_limiter = (
        InMemoryRateLimiter(
            requests_per_second=CLOUD_EVAL_REQUESTS_PER_SECOND,
            check_every_n_seconds=0.1,
            max_bucket_size=1,
        )
        if provider is AgentProvider.GEMINI
        else None
    )
    selected = [
        scenario
        for scenario in load_scenarios()
        if scenario_ids is None or scenario.scenario_id in scenario_ids
    ]
    results = []
    traces = []
    preferred_cloud_slot = 0
    abort_reason = None
    for scenario in selected:
        started = time.perf_counter()
        print(f"EVAL_START {scenario.scenario_id}", flush=True)
        attempts: list[dict[str, str]] = []
        key_slot: str | None = None
        scenario_abort = None
        if provider is AgentProvider.GEMINI:
            (
                trace,
                evaluation,
                preferred_cloud_slot,
                attempts,
                scenario_abort,
            ) = _run_cloud_scenario_with_failover(
                scenario,
                settings=settings,
                slots=cloud_slots,
                start_index=preferred_cloud_slot,
                rate_limiter=cloud_rate_limiter,
            )
            key_slot = cloud_slots[preferred_cloud_slot].label
        else:
            trace, evaluation = run_scenario(scenario, settings=settings)
        results.append(evaluation)
        traces.append(
            {
                "scenario_id": scenario.scenario_id,
                "key_slot": key_slot,
                "attempts": attempts,
                "trace": asdict(trace),
            }
        )
        print(
            f"EVAL_DONE {scenario.scenario_id} "
            f"seconds={time.perf_counter() - started:.2f} "
            f"e2e={int(evaluation.end_to_end_pass)} error={int(trace.error is not None)}",
            flush=True,
        )
        if scenario_abort is not None:
            abort_reason = scenario_abort
            print(
                f"EVAL_ABORT {scenario.scenario_id} reason={scenario_abort}",
                flush=True,
            )
            break
    payload = {
        "provider": provider.value,
        "model": settings.selected_model,
        "metrics": asdict(EvaluationMetrics.from_results(results)),
        "requested_scenario_count": len(selected),
        "aborted": abort_reason is not None,
        "abort_reason": abort_reason,
        "results": [asdict(item) for item in results],
        "traces": traces,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return payload
