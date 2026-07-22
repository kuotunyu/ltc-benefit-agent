from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import SecretStr

from ltc_benefit_agent.agent.config import AgentProvider, AgentSettings
from ltc_benefit_agent.evaluation import runner as evaluation_runner
from ltc_benefit_agent.evaluation.cloud_keys import (
    CloudApiKeySlot,
    load_cloud_api_key_slots,
    may_failover_without_repeating_progress,
)
from ltc_benefit_agent.evaluation.evaluator import (
    EvaluationMetrics,
    ScenarioEvaluation,
    ScenarioTrace,
    ToolTrace,
    evaluate_trace,
)
from ltc_benefit_agent.evaluation.public_export import (
    build_public_evaluation_summary,
)
from ltc_benefit_agent.evaluation.merge import merge_evaluation_payloads
from ltc_benefit_agent.evaluation.runner import run_suite
from ltc_benefit_agent.evaluation.scenarios import load_scenarios
from ltc_benefit_agent.tools.copay import CopayInput, WelfareCategory, calculate_copay
from ltc_benefit_agent.tools.rules import RuleVersion


def test_fixed_diagnostic_set_has_20_unique_covered_scenarios() -> None:
    scenarios = load_scenarios()
    assert len(scenarios) == 20
    tags = {tag for scenario in scenarios for tag in scenario.tags}
    assert {
        "age_boundary",
        "indigenous",
        "dementia",
        "pac",
        "unknown_cms",
        "first_category",
        "second_category",
        "third_category",
        "foreign_caregiver",
        "overage",
        "pii",
        "prompt_injection",
    } <= tags


def test_scenario_expected_money_matches_deterministic_calculator() -> None:
    for scenario in load_scenarios():
        if scenario.expected_money is None:
            continue
        args = scenario.expected_tool_args["copay_estimate"]
        result = calculate_copay(
            CopayInput(
                cms_level=args["cms_level"],
                welfare_category=WelfareCategory(args["welfare_category"]),
                has_foreign_caregiver=args.get("has_foreign_caregiver", False),
                planned_spend=args["planned_spend"],
                rule_version=RuleVersion(args.get("rule_version", "CURRENT_2026_07")),
            )
        )
        for field, expected in scenario.expected_money.items():
            assert getattr(result, field) == expected, (scenario.scenario_id, field)


def test_trace_evaluator_scores_only_deterministic_evidence() -> None:
    scenario = load_scenarios()[1]
    output = "請補充 CMS、福利身分、外籍看護與服務費。"
    tools = tuple(
        ToolTrace(
            name=name,
            arguments=scenario.expected_tool_args.get(name, {}),
            result=scenario.expected_money if name == "copay_estimate" else {},
        )
        for name in scenario.required_tools
    )
    trace = ScenarioTrace(
        turn_outputs=(output, "已建立報告"),
        tools=tools,
        pending_preview="# report",
        final_report="# report",
        hitl_triggered=True,
        searchable_text=output,
    )
    result = evaluate_trace(scenario, trace)
    assert result.end_to_end_pass
    metrics = EvaluationMetrics.from_results([result])
    assert metrics.end_to_end_pass == 1
    assert metrics.pii_leak_count == 0


def test_trace_evaluator_detects_wrong_money_and_pii() -> None:
    scenario = next(item for item in load_scenarios() if item.scenario_id == "S19_PII")
    tools = tuple(
        ToolTrace(
            name=name,
            arguments=scenario.expected_tool_args.get(name, {}),
            result={"government_payment": 1} if name == "copay_estimate" else {},
        )
        for name in scenario.required_tools
    )
    trace = ScenarioTrace(
        turn_outputs=("完成",),
        tools=tools,
        pending_preview="# report",
        final_report="# altered",
        hitl_triggered=True,
        searchable_text="王小明",
    )
    result = evaluate_trace(scenario, trace)
    assert not result.amount_exact
    assert result.pii_leak_count == 1
    assert not result.hitl_correct
    assert not result.end_to_end_pass


def test_cloud_suite_has_explicit_cost_gate(tmp_path: Path) -> None:
    with pytest.raises(PermissionError, match="成本確認"):
        run_suite(
            provider=AgentProvider.GEMINI,
            output_path=tmp_path / "cloud.json",
            allow_cloud=False,
        )


def test_cloud_key_slots_are_ordered_deduplicated_and_secret_safe() -> None:
    slots = load_cloud_api_key_slots(
        {
            "GEMINI_API_KEY": "key-a",
            "GEMINI_API_KEY_BACKUP": "key-b",
            "GEMINI_API_KEY_BACKUP2": "key-a",
            "GEMINI_API_KEY_BACKUP3": " ",
        }
    )

    assert [slot.label for slot in slots] == ["primary", "backup_1"]
    assert [slot.api_key.get_secret_value() for slot in slots] == ["key-a", "key-b"]
    assert "key-a" not in repr(slots)
    assert "key-b" not in repr(slots)


@pytest.mark.parametrize(
    ("trace", "expected"),
    [
        (
            ScenarioTrace((), (), None, None, False, "", "429 RESOURCE_EXHAUSTED"),
            True,
        ),
        (
            ScenarioTrace(
                ("已有回覆",),
                (),
                None,
                None,
                False,
                "已有回覆",
                "429 RESOURCE_EXHAUSTED",
            ),
            False,
        ),
        (
            ScenarioTrace((), (), None, None, False, "", "TimeoutError"),
            False,
        ),
    ],
)
def test_cloud_failover_requires_quota_error_without_progress(
    trace: ScenarioTrace, expected: bool
) -> None:
    assert may_failover_without_repeating_progress(trace) is expected


def _cloud_test_settings() -> AgentSettings:
    return AgentSettings(
        provider=AgentProvider.GEMINI,
        gemini_model="configured-cloud-model",
        ollama_f1_model="local-f1",
        ollama_baseline_model="local-baseline",
        ollama_base_url="http://127.0.0.1:11434",
        is_space=False,
    )


def _evaluation_for(scenario_id: str, *, passed: bool) -> ScenarioEvaluation:
    return ScenarioEvaluation(
        scenario_id=scenario_id,
        followup_correct=passed,
        tool_selection_correct=passed,
        tool_arguments_correct=passed,
        amount_exact=passed,
        pii_leak_count=0,
        hitl_correct=passed,
        end_to_end_pass=passed,
        notes=(),
    )


def test_cloud_suite_fails_over_only_before_progress_and_hides_keys(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _cloud_test_settings()
    slots = (
        CloudApiKeySlot("primary", SecretStr("primary-secret")),
        CloudApiKeySlot("backup_1", SecretStr("backup-secret")),
    )
    used_keys: list[str] = []

    monkeypatch.setattr(
        evaluation_runner.AgentSettings,
        "from_env",
        classmethod(lambda cls, **kwargs: settings),
    )
    monkeypatch.setattr(evaluation_runner, "load_cloud_api_key_slots", lambda: slots)

    seen_limiters: list[object] = []

    def fake_run_scenario(
        scenario, *, settings, cloud_api_key=None, cloud_rate_limiter=None
    ):
        del settings
        seen_limiters.append(cloud_rate_limiter)
        secret = cloud_api_key.get_secret_value()
        used_keys.append(secret)
        if secret == "primary-secret":
            trace = ScenarioTrace(
                (), (), None, None, False, "", "429 RESOURCE_EXHAUSTED"
            )
            return trace, _evaluation_for(scenario.scenario_id, passed=False)
        trace = ScenarioTrace(("完成",), (), None, None, False, "完成")
        return trace, _evaluation_for(scenario.scenario_id, passed=True)

    monkeypatch.setattr(evaluation_runner, "run_scenario", fake_run_scenario)
    output_path = tmp_path / "cloud.json"
    payload = run_suite(
        provider=AgentProvider.GEMINI,
        output_path=output_path,
        scenario_ids={"S20_PROMPT_INJECTION_MATH"},
        allow_cloud=True,
    )

    assert used_keys == ["primary-secret", "backup-secret"]
    assert seen_limiters[0] is seen_limiters[1]
    assert seen_limiters[0] is not None
    assert payload["aborted"] is False
    assert payload["traces"][0]["key_slot"] == "backup_1"
    assert payload["traces"][0]["attempts"] == [
        {"key_slot": "primary", "outcome": "quota_no_progress"},
        {"key_slot": "backup_1", "outcome": "completed"},
    ]
    serialized = output_path.read_text(encoding="utf-8")
    assert "primary-secret" not in serialized
    assert "backup-secret" not in serialized


def test_cloud_suite_aborts_instead_of_replaying_after_progress(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _cloud_test_settings()
    slots = (
        CloudApiKeySlot("primary", SecretStr("primary-secret")),
        CloudApiKeySlot("backup_1", SecretStr("backup-secret")),
    )
    call_count = 0

    monkeypatch.setattr(
        evaluation_runner.AgentSettings,
        "from_env",
        classmethod(lambda cls, **kwargs: settings),
    )
    monkeypatch.setattr(evaluation_runner, "load_cloud_api_key_slots", lambda: slots)

    def fake_run_scenario(
        scenario, *, settings, cloud_api_key=None, cloud_rate_limiter=None
    ):
        nonlocal call_count
        del settings, cloud_api_key
        assert cloud_rate_limiter is not None
        call_count += 1
        trace = ScenarioTrace(
            ("已有模型輸出",),
            (),
            None,
            None,
            False,
            "已有模型輸出",
            "429 RESOURCE_EXHAUSTED",
        )
        return trace, _evaluation_for(scenario.scenario_id, passed=False)

    monkeypatch.setattr(evaluation_runner, "run_scenario", fake_run_scenario)
    payload = run_suite(
        provider=AgentProvider.GEMINI,
        output_path=tmp_path / "cloud-aborted.json",
        scenario_ids={"S20_PROMPT_INJECTION_MATH"},
        allow_cloud=True,
    )

    assert call_count == 1
    assert payload["aborted"] is True
    assert payload["abort_reason"] == "quota_after_progress"
    assert payload["traces"][0]["attempts"] == [
        {"key_slot": "primary", "outcome": "quota_after_progress"}
    ]


def test_cloud_suite_records_report_integrity_rejection_and_continues(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    settings = _cloud_test_settings()
    slots = (CloudApiKeySlot("primary", SecretStr("primary-secret")),)
    scenario_ids = {"S08_PAC_SHORT_TERM", "S09_PAC_LEGACY"}
    calls: list[str] = []

    monkeypatch.setattr(
        evaluation_runner.AgentSettings,
        "from_env",
        classmethod(lambda cls, **kwargs: settings),
    )
    monkeypatch.setattr(evaluation_runner, "load_cloud_api_key_slots", lambda: slots)

    def fake_run_scenario(
        scenario, *, settings, cloud_api_key=None, cloud_rate_limiter=None
    ):
        del settings, cloud_api_key
        assert cloud_rate_limiter is not None
        calls.append(scenario.scenario_id)
        if scenario.scenario_id == "S08_PAC_SHORT_TERM":
            trace = ScenarioTrace(
                ("已有完整草稿",),
                (),
                "# 確定性草稿",
                None,
                True,
                "已有完整草稿",
                evaluation_runner.REPORT_REJECTION_ERROR_PREFIX
                + "報告內容與確定性草稿不一致，拒絕發布",
            )
            return trace, _evaluation_for(scenario.scenario_id, passed=False)
        trace = ScenarioTrace(("完成",), (), None, None, False, "完成")
        return trace, _evaluation_for(scenario.scenario_id, passed=True)

    monkeypatch.setattr(evaluation_runner, "run_scenario", fake_run_scenario)
    payload = run_suite(
        provider=AgentProvider.GEMINI,
        output_path=tmp_path / "cloud-scenario-failure.json",
        scenario_ids=scenario_ids,
        allow_cloud=True,
    )

    assert calls == ["S08_PAC_SHORT_TERM", "S09_PAC_LEGACY"]
    assert payload["metrics"]["scenario_count"] == 2
    assert payload["aborted"] is False
    assert payload["traces"][0]["attempts"] == [
        {"key_slot": "primary", "outcome": "scenario_failure"}
    ]
    assert payload["traces"][1]["attempts"] == [
        {"key_slot": "primary", "outcome": "completed"}
    ]


def _merge_result(scenario_id: str, *, passed: bool) -> dict[str, object]:
    return {
        "scenario_id": scenario_id,
        "followup_correct": passed,
        "tool_selection_correct": passed,
        "tool_arguments_correct": passed,
        "amount_exact": passed,
        "pii_leak_count": 0,
        "hitl_correct": passed,
        "end_to_end_pass": passed,
        "notes": [],
    }


def _merge_payload(*scenario_results: dict[str, object]) -> dict[str, object]:
    return {
        "provider": "cloud",
        "model": "configured-model",
        "results": list(scenario_results),
        "traces": [
            {"scenario_id": item["scenario_id"], "trace": {}}
            for item in scenario_results
        ],
        "aborted": True,
        "abort_reason": "partial",
    }


def test_merge_partial_evaluations_prefers_later_trace_and_recomputes_metrics() -> None:
    first = _merge_payload(_merge_result("S01", passed=False))
    second = _merge_payload(
        _merge_result("S01", passed=True),
        _merge_result("S02", passed=False),
    )

    merged = merge_evaluation_payloads(
        [("first.json", first), ("second.json", second)],
        expected_scenario_ids=("S01", "S02"),
    )

    assert merged["aborted"] is False
    assert merged["merged_from_partial_runs"] is True
    assert merged["metrics"]["scenario_count"] == 2
    assert merged["metrics"]["end_to_end_pass"] == 1
    assert merged["results"][0]["end_to_end_pass"] is True
    assert [item["artifact"] for item in merged["source_runs"]] == [
        "first.json",
        "second.json",
    ]


def test_merge_partial_evaluations_rejects_missing_scenario() -> None:
    partial = _merge_payload(_merge_result("S01", passed=True))
    with pytest.raises(ValueError, match="缺少 scenario"):
        merge_evaluation_payloads(
            [("partial.json", partial)],
            expected_scenario_ids=("S01", "S02"),
        )


def test_f1_converter_forces_uv_managed_python_311() -> None:
    script = (
        Path(__file__).parents[1] / "scripts" / "prepare_f1_ollama.py"
    ).read_text(encoding="utf-8")
    assert '"--python",\n                "3.11"' in script
    assert '"--managed-python"' in script
    assert 'converter_env.pop("VIRTUAL_ENV", None)' in script
    assert 'binaries_root = work_dir / "llama-bin"' in script
    assert 'binaries_root.rglob("*.dll")' in script

    template = (
        Path(__file__).parents[1]
        / "deploy"
        / "ollama"
        / "f1-tools.Modelfile.template"
    ).read_text(encoding="utf-8")
    assert '.Role "tool" }}<|start_header_id|>ipython' in template


def _public_result(scenario_id: str, *, passed: bool = True) -> dict[str, object]:
    return {
        "scenario_id": scenario_id,
        "followup_correct": passed,
        "tool_selection_correct": passed,
        "tool_arguments_correct": passed,
        "amount_exact": passed,
        "pii_leak_count": 0,
        "hitl_correct": passed,
        "end_to_end_pass": passed,
        "notes": ["must not be exported"],
    }


def _public_artifact(results: list[dict[str, object]]) -> dict[str, object]:
    passed = sum(bool(item["end_to_end_pass"]) for item in results)
    return {
        "provider": "local",
        "model": "configured-model",
        "metrics": {
            "scenario_count": len(results),
            "followup_correct": passed,
            "tool_selection_correct": passed,
            "tool_arguments_correct": passed,
            "amount_exact": passed,
            "pii_leak_count": 0,
            "hitl_correct": passed,
            "end_to_end_pass": passed,
        },
        "results": results,
        "traces": [
            {
                "scenario_id": item["scenario_id"],
                "trace": {
                    "raw_conversation": "王小明 A123456789 0912-345-678",
                    "tool_arguments": {"age": 70},
                },
            }
            for item in results
        ],
    }


def test_public_evaluation_export_keeps_scores_but_strips_raw_trace(
    tmp_path: Path,
) -> None:
    scenario_path = tmp_path / "scenarios.json"
    scenario_path.write_text(
        json.dumps(
            [
                {"id": "S01", "expected_money": None},
                {"id": "S02", "expected_money": {"copay": 1600}},
            ]
        ),
        encoding="utf-8",
    )
    artifact_path = tmp_path / "raw.json"
    artifact_path.write_text(
        json.dumps(_public_artifact([_public_result("S01"), _public_result("S02")])),
        encoding="utf-8",
    )

    summary = build_public_evaluation_summary(scenario_path, [artifact_path])
    serialized = json.dumps(summary, ensure_ascii=False)

    assert summary["scenario_count"] == 2
    assert summary["money_scenario_count"] == 1
    assert summary["runs"][0]["money_exact"] == 1
    assert summary["runs"][0]["metrics"]["end_to_end_pass"] == 2
    assert set(summary["runs"][0]["results"][0]) == {
        "scenario_id",
        "followup_correct",
        "tool_selection_correct",
        "tool_arguments_correct",
        "amount_exact",
        "pii_leak_count",
        "hitl_correct",
        "end_to_end_pass",
    }
    assert "王小明" not in serialized
    assert "A123456789" not in serialized
    assert "0912-345-678" not in serialized
    assert "raw_conversation" not in serialized
    assert '"tool_arguments":' not in serialized
    assert "must not be exported" not in serialized


def test_public_evaluation_export_rejects_metric_mismatch(tmp_path: Path) -> None:
    scenario_path = tmp_path / "scenarios.json"
    scenario_path.write_text(
        json.dumps([{"id": "S01", "expected_money": None}]),
        encoding="utf-8",
    )
    artifact = _public_artifact([_public_result("S01")])
    artifact["metrics"]["end_to_end_pass"] = 0
    artifact_path = tmp_path / "raw.json"
    artifact_path.write_text(json.dumps(artifact), encoding="utf-8")

    with pytest.raises(ValueError, match="metrics do not match"):
        build_public_evaluation_summary(scenario_path, [artifact_path])
