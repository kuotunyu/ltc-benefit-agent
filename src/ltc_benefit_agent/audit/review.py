"""Deterministic zh-TW review reports for rule-audit evidence."""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping, Sequence

from .consistency import ConsistencyCheckResult, ConsistencyStatus
from .models import ChangedField, RuleAuditResult, RuleAuditStatus


class ReviewDecision(StrEnum):
    """Human decision recorded in an evidence report."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


_STATUS_LABELS = {
    RuleAuditStatus.VERIFIED_SNAPSHOT: "語意與核准快照一致",
    RuleAuditStatus.REVIEW_REQUIRED: "偵測到差異，需人工複核",
    RuleAuditStatus.CHECK_UNAVAILABLE: "本次查證不可用，不可視為通過",
}

_FIELD_LABELS = {
    "eligibility.minimum_age": "一般年齡門檻",
    "eligibility.indigenous_minimum_age": "原住民年齡門檻",
    "eligibility.dementia_minimum_age": "失智症年齡門檻",
    "eligibility.disability_certificate": "身心障礙證明資格",
    "eligibility.pac_eligible": "PAC 資格",
    "care_and_professional_monthly": "照顧及專業服務月額",
    "percentage_matrix.care_and_professional": "照顧及專業服務部分負擔",
    "foreign_caregiver.quota_percent": "外籍家庭看護等情形額度比例",
    "foreign_caregiver.usage_scope": "外籍家庭看護等情形使用範圍",
    "extractor.required_structure": "官方來源必要結構",
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _markdown_cell(value: Any) -> str:
    return _json(value).replace("|", "\\|").replace("\n", "<br>")


def _field_label(path: str) -> str:
    if path in _FIELD_LABELS:
        return _FIELD_LABELS[path]
    for suffix, label in _FIELD_LABELS.items():
        if path.endswith(suffix):
            return label
    return path


def _suggested_tests(path: str, impacted_rule_ids: Sequence[str]) -> str:
    text = f"{path} {' '.join(impacted_rule_ids)}".lower()
    if "eligibility" in text or "age" in text or "residence" in text:
        return "重跑資格矩陣、年齡邊界、住宿排除與舊現制差異測試。"
    if "quota" in text or "monthly" in text:
        return "重跑 CMS 2–8 額度矩陣、外籍看護 30% 與超額使用測試。"
    if "copay" in text or "percentage" in text:
        return "重跑三福利類別部分負擔、無條件捨去與非法輸入測試。"
    if "foreign_caregiver" in text:
        return "重跑外籍看護調整額度與法定使用範圍測試。"
    if "effective" in text or "amended" in text:
        return "重跑規則版本、施行日期與報告 metadata 測試。"
    if "extractor" in text:
        return "更新離線 fixture 前先人工檢查官方版面，再重跑 extractor 結構測試。"
    return "依受影響規則 ID 補齊 fixture、單元測試與完整回歸測試。"


def audit_result_from_mapping(data: Mapping[str, Any]) -> RuleAuditResult:
    """Strictly reconstruct one read-only audit result from JSON evidence."""

    required = {
        "source_id",
        "title",
        "canonical_url",
        "rule_version",
        "effective_date",
        "checked_at",
        "status",
        "fetch_result",
        "http_status",
        "raw_sha256_expected",
        "raw_sha256_actual",
        "semantic_fingerprint_expected",
        "semantic_fingerprint_actual",
        "changed_fields",
        "errors",
        "writes_performed",
    }
    missing = sorted(required - data.keys())
    if missing:
        raise ValueError(f"Audit result is missing fields: {', '.join(missing)}")
    if data["writes_performed"] is not False:
        raise ValueError("Audit evidence must report writes_performed=false")
    changed_fields = tuple(
        ChangedField(
            path=str(item["path"]),
            expected=item["expected"],
            actual=item["actual"],
            impacted_rule_ids=tuple(str(value) for value in item["impacted_rule_ids"]),
        )
        for item in data["changed_fields"]
    )
    return RuleAuditResult(
        source_id=str(data["source_id"]),
        title=str(data["title"]),
        canonical_url=str(data["canonical_url"]),
        rule_version=str(data["rule_version"]),
        effective_date=str(data["effective_date"]),
        checked_at=str(data["checked_at"]),
        status=RuleAuditStatus(str(data["status"])),
        fetch_result=str(data["fetch_result"]),
        http_status=(
            None if data["http_status"] is None else int(data["http_status"])
        ),
        raw_sha256_expected=str(data["raw_sha256_expected"]),
        raw_sha256_actual=(
            None
            if data["raw_sha256_actual"] is None
            else str(data["raw_sha256_actual"])
        ),
        semantic_fingerprint_expected=str(
            data["semantic_fingerprint_expected"]
        ),
        semantic_fingerprint_actual=(
            None
            if data["semantic_fingerprint_actual"] is None
            else str(data["semantic_fingerprint_actual"])
        ),
        changed_fields=changed_fields,
        errors=tuple(str(value) for value in data["errors"]),
        writes_performed=False,
    )


def load_audit_evidence(
    path: str | Path,
) -> tuple[str, tuple[RuleAuditResult, ...]]:
    """Load a P1 JSON artifact without contacting official sources."""

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema_version") != "1":
        raise ValueError("Unsupported audit evidence schema_version")
    if data.get("writes_performed") is not False:
        raise ValueError("Audit evidence must report writes_performed=false")
    results = tuple(
        audit_result_from_mapping(item) for item in data.get("results", ())
    )
    if not results:
        raise ValueError("Audit evidence must contain at least one result")
    return str(data["manifest_version"]), results


def render_review_report(
    results: Sequence[RuleAuditResult],
    consistency: ConsistencyCheckResult,
    *,
    manifest_version: str,
    decision: ReviewDecision = ReviewDecision.PENDING,
    review_note: str = "",
) -> str:
    """Render stable, LLM-free Markdown for author review."""

    if not results:
        raise ValueError("At least one audit result is required")
    decision_text = {
        ReviewDecision.PENDING: "待作者複核",
        ReviewDecision.APPROVED: "作者已核准；後續仍須另開小功能更新規則",
        ReviewDecision.REJECTED: "作者已拒絕；現行核准快照保持不變",
    }[decision]
    lines = [
        "# 長照規則來源人工複核報告",
        "",
        "> 本報告由確定性 Python 程式產生，不使用 LLM 判斷法規差異，"
        "也不會修改資格、額度或部分負擔常數。",
        "",
        f"- manifest 版本：`{manifest_version}`",
        f"- 人工決定：**{decision_text}**",
        "- `writes_performed`：`false`",
        "",
        "## 來源查證摘要",
        "",
        "| 來源 | 規則版本 | 查證結果 | 查證時間 |",
        "|---|---|---|---|",
    ]
    for result in results:
        lines.append(
            f"| [{result.title}]({result.canonical_url}) | "
            f"`{result.rule_version}` | {_STATUS_LABELS[result.status]} | "
            f"`{result.checked_at}` |"
        )

    changed = [
        (result, field)
        for result in results
        for field in result.changed_fields
    ]
    lines.extend(["", "## 欄位級差異", ""])
    if not changed:
        lines.append("- 差異欄位：無（未偵測到欄位級語意差異）。")
    else:
        lines.extend(
            [
                "| 來源 | 欄位 | 核准舊值 | 官方觀察新值 | 影響規則 | 建議測試 |",
                "|---|---|---|---|---|---|",
            ]
        )
        for result, field in changed:
            lines.append(
                f"| `{result.source_id}` | {_field_label(field.path)} "
                f"(`{field.path}`) | {_markdown_cell(field.expected)} | "
                f"{_markdown_cell(field.actual)} | "
                f"{', '.join(f'`{value}`' for value in field.impacted_rule_ids)} | "
                f"{_suggested_tests(field.path, field.impacted_rule_ids)} |"
            )

    unavailable = [
        result for result in results if result.status is RuleAuditStatus.CHECK_UNAVAILABLE
    ]
    if unavailable:
        lines.extend(["", "## 無法查證項目", ""])
        for result in unavailable:
            error_text = "；".join(result.errors) or result.fetch_result
            lines.append(f"- `{result.source_id}`：{error_text}")
        lines.append("- 上述項目不可視為通過，應稍後重新查證。")

    lines.extend(
        [
            "",
            "## 專案一致性",
            "",
            f"- 結果：`{consistency.status.value}`",
            f"- 檢查範圍：{', '.join(f'`{item}`' for item in consistency.checked_targets)}",
            "- `writes_performed`：`false`",
        ]
    )
    if consistency.status is ConsistencyStatus.CONSISTENT:
        lines.append("- manifest、執行期規則、README、fixture 與測試預期值一致。")
    else:
        lines.extend(
            [
                "",
                "| 範圍 | 欄位 | manifest／核准值 | 專案觀察值 | 建議處置 |",
                "|---|---|---|---|---|",
            ]
        )
        for issue in consistency.issues:
            lines.append(
                f"| `{issue.scope}` | `{issue.path}` | "
                f"{_markdown_cell(issue.expected)} | {_markdown_cell(issue.actual)} | "
                f"{issue.recommendation} |"
            )

    lines.extend(
        [
            "",
            "## 人工處置",
            "",
            "1. 逐項對照官方來源、舊值、新值與受影響規則。",
            "2. 若拒絕差異，保留現行核准快照與業務常數，不做任何發布。",
            "3. 若核准差異，另開小功能更新規則、README 與回歸測試；"
            "本報告本身不授權自動改值。",
        ]
    )
    if review_note:
        lines.extend(["", f"- 複核備註：{review_note}"])
    return "\n".join(lines) + "\n"
