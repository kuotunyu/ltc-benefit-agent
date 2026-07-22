"""離線合併固定診斷集的 partial artifacts，保留來源與中止證據。"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .evaluator import EvaluationMetrics, ScenarioEvaluation


def _scenario_result(data: Mapping[str, Any]) -> ScenarioEvaluation:
    return ScenarioEvaluation(
        scenario_id=str(data["scenario_id"]),
        followup_correct=bool(data["followup_correct"]),
        tool_selection_correct=bool(data["tool_selection_correct"]),
        tool_arguments_correct=bool(data["tool_arguments_correct"]),
        amount_exact=bool(data["amount_exact"]),
        pii_leak_count=int(data["pii_leak_count"]),
        hitl_correct=bool(data["hitl_correct"]),
        end_to_end_pass=bool(data["end_to_end_pass"]),
        notes=tuple(str(item) for item in data.get("notes", ())),
    )


def merge_evaluation_payloads(
    sources: Sequence[tuple[str, Mapping[str, Any]]],
    *,
    expected_scenario_ids: Sequence[str],
) -> dict[str, Any]:
    """依來源順序合併；同一 scenario 由較晚來源覆蓋較早 partial。"""

    if not sources:
        raise ValueError("至少需要一份 evaluation artifact")
    expected = tuple(expected_scenario_ids)
    if len(expected) != len(set(expected)):
        raise ValueError("expected_scenario_ids 不得重複")

    provider = str(sources[0][1]["provider"])
    model = str(sources[0][1]["model"])
    expected_set = set(expected)
    result_by_id: dict[str, Mapping[str, Any]] = {}
    trace_by_id: dict[str, Mapping[str, Any]] = {}
    source_runs: list[dict[str, Any]] = []

    for source_name, payload in sources:
        if str(payload["provider"]) != provider or str(payload["model"]) != model:
            raise ValueError("所有 artifacts 必須使用相同 provider 與 model")
        results = {
            str(item["scenario_id"]): item for item in payload.get("results", ())
        }
        traces = {
            str(item["scenario_id"]): item for item in payload.get("traces", ())
        }
        if set(results) != set(traces):
            raise ValueError(f"{source_name} 的 results／traces scenario 不一致")
        unexpected = set(results) - expected_set
        if unexpected:
            raise ValueError(f"{source_name} 含非預期 scenario: {sorted(unexpected)}")
        result_by_id.update(results)
        trace_by_id.update(traces)
        source_runs.append(
            {
                "artifact": Path(source_name).name,
                "recorded_scenario_count": len(results),
                "aborted": bool(payload.get("aborted", False)),
                "abort_reason": payload.get("abort_reason"),
            }
        )

    missing = [scenario_id for scenario_id in expected if scenario_id not in result_by_id]
    if missing:
        raise ValueError(f"合併後仍缺少 scenario: {missing}")

    results = [_scenario_result(result_by_id[item]) for item in expected]
    return {
        "provider": provider,
        "model": model,
        "metrics": asdict(EvaluationMetrics.from_results(results)),
        "requested_scenario_count": len(expected),
        "aborted": False,
        "abort_reason": None,
        "merged_from_partial_runs": True,
        "source_runs": source_runs,
        "results": [asdict(item) for item in results],
        "traces": [dict(trace_by_id[item]) for item in expected],
    }


def merge_evaluation_artifacts(
    input_paths: Sequence[Path],
    *,
    output_path: Path,
    expected_scenario_ids: Sequence[str],
) -> dict[str, Any]:
    sources = [
        (path.name, json.loads(path.read_text(encoding="utf-8")))
        for path in input_paths
    ]
    payload = merge_evaluation_payloads(
        sources,
        expected_scenario_ids=expected_scenario_ids,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload
