"""將 ignored raw evaluation artifact 匯出成可公開、無對話內容的摘要。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


RESULT_FIELDS = (
    "scenario_id",
    "followup_correct",
    "tool_selection_correct",
    "tool_arguments_correct",
    "amount_exact",
    "pii_leak_count",
    "hitl_correct",
    "end_to_end_pass",
)
METRIC_FIELDS = (
    "scenario_count",
    "followup_correct",
    "tool_selection_correct",
    "tool_arguments_correct",
    "amount_exact",
    "pii_leak_count",
    "hitl_correct",
    "end_to_end_pass",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return data


def _recompute_metrics(results: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "scenario_count": len(results),
        "followup_correct": sum(bool(item["followup_correct"]) for item in results),
        "tool_selection_correct": sum(
            bool(item["tool_selection_correct"]) for item in results
        ),
        "tool_arguments_correct": sum(
            bool(item["tool_arguments_correct"]) for item in results
        ),
        "amount_exact": sum(bool(item["amount_exact"]) for item in results),
        "pii_leak_count": sum(int(item["pii_leak_count"]) for item in results),
        "hitl_correct": sum(bool(item["hitl_correct"]) for item in results),
        "end_to_end_pass": sum(bool(item["end_to_end_pass"]) for item in results),
    }


def build_public_evaluation_summary(
    scenario_path: Path,
    artifact_paths: Iterable[Path],
) -> dict[str, Any]:
    """驗證 raw artifacts，並只保留布林評分、模型標籤與雜湊。

    對話、tool arguments、tool results、attempt details 與 evaluator notes 一律不輸出。
    """

    scenario_data = json.loads(scenario_path.read_text(encoding="utf-8"))
    if not isinstance(scenario_data, list) or not scenario_data:
        raise ValueError("scenario file must contain a non-empty list")
    scenario_ids = [str(item["id"]) for item in scenario_data]
    if len(scenario_ids) != len(set(scenario_ids)):
        raise ValueError("scenario IDs must be unique")
    money_ids = {
        str(item["id"])
        for item in scenario_data
        if item.get("expected_money") is not None
    }

    runs: list[dict[str, Any]] = []
    for artifact_path in artifact_paths:
        artifact = _load_object(artifact_path)
        raw_results = artifact.get("results")
        raw_traces = artifact.get("traces")
        if not isinstance(raw_results, list) or not isinstance(raw_traces, list):
            raise ValueError(f"artifact is missing results or traces: {artifact_path}")

        results: list[dict[str, Any]] = []
        for item in raw_results:
            if not isinstance(item, dict) or any(field not in item for field in RESULT_FIELDS):
                raise ValueError(f"invalid result row in {artifact_path}")
            results.append({field: item[field] for field in RESULT_FIELDS})

        result_ids = [str(item["scenario_id"]) for item in results]
        if result_ids != scenario_ids:
            raise ValueError(
                f"artifact scenario order or coverage differs from scenario file: {artifact_path}"
            )
        if len(raw_traces) != len(scenario_ids):
            raise ValueError(f"artifact trace count mismatch: {artifact_path}")

        metrics = _recompute_metrics(results)
        recorded_metrics = artifact.get("metrics")
        if not isinstance(recorded_metrics, dict):
            raise ValueError(f"artifact metrics are missing: {artifact_path}")
        normalized_recorded = {
            field: int(recorded_metrics[field]) for field in METRIC_FIELDS
        }
        if metrics != normalized_recorded:
            raise ValueError(f"artifact metrics do not match result rows: {artifact_path}")

        runs.append(
            {
                "provider": str(artifact["provider"]),
                "model": str(artifact["model"]),
                "source_artifact": artifact_path.name,
                "source_sha256": _sha256(artifact_path),
                "trace_count": len(raw_traces),
                "metrics": metrics,
                "money_scenario_count": len(money_ids),
                "money_exact": sum(
                    bool(item["amount_exact"])
                    for item in results
                    if str(item["scenario_id"]) in money_ids
                ),
                "results": results,
            }
        )

    if not runs:
        raise ValueError("at least one evaluation artifact is required")
    return {
        "schema_version": 1,
        "diagnostic_set": scenario_path.as_posix(),
        "diagnostic_set_sha256": _sha256(scenario_path),
        "scenario_count": len(scenario_ids),
        "money_scenario_count": len(money_ids),
        "privacy": (
            "Only deterministic per-scenario scores are public; raw conversation, "
            "tool arguments, tool results and attempts are excluded."
        ),
        "limitations": (
            "This is a fixed 20-scenario diagnostic set, not a statistical "
            "generalization claim or permission for unsupervised use."
        ),
        "runs": runs,
    }


def write_public_evaluation_summary(
    scenario_path: Path,
    artifact_paths: Iterable[Path],
    output_path: Path,
) -> dict[str, Any]:
    summary = build_public_evaluation_summary(scenario_path, artifact_paths)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary
