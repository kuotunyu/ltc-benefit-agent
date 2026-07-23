"""Minimized public status views for deterministic rule-source audits."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any, Mapping, Sequence

from .manifest import load_manifest
from .models import RuleAuditResult, RuleAuditStatus


_STATUS_PRIORITY = {
    RuleAuditStatus.VERIFIED_SNAPSHOT: 0,
    RuleAuditStatus.REVIEW_REQUIRED: 1,
    RuleAuditStatus.CHECK_UNAVAILABLE: 2,
}


def _parse_audit_timestamp(value: str) -> datetime:
    """Parse one audit timestamp and require an unambiguous timezone."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Rule audit checked_at must include a timezone")
    return parsed


def _canonical_utc_timestamp(value: datetime) -> str:
    """Render a stable public timestamp independent of source offsets."""

    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def build_public_audit_summary(
    results: Sequence[RuleAuditResult],
    *,
    manifest_version: str,
    expected_source_ids: Sequence[str],
) -> dict[str, Any]:
    """Return a whitelist-only summary safe for a public CI artifact."""

    if not results:
        raise ValueError("Public audit summary requires at least one result")
    if not isinstance(manifest_version, str) or not manifest_version.strip():
        raise ValueError("Public audit summary manifest_version is required")
    ordered = tuple(sorted(results, key=lambda result: result.source_id))
    actual_source_ids = tuple(result.source_id for result in ordered)
    if len(actual_source_ids) != len(set(actual_source_ids)):
        raise ValueError("Public audit summary source_id values must be unique")
    if isinstance(expected_source_ids, (str, bytes)):
        raise ValueError(
            "Expected public audit source_id values must be a sequence of strings"
        )
    expected = tuple(expected_source_ids)
    if not expected:
        raise ValueError("Expected public audit source_id values cannot be empty")
    if not all(isinstance(source_id, str) and source_id for source_id in expected):
        raise ValueError(
            "Expected public audit source_id values must be non-empty strings"
        )
    if len(expected) != len(set(expected)):
        raise ValueError("Expected public audit source_id values must be unique")
    if set(actual_source_ids) != set(expected):
        missing = sorted(set(expected) - set(actual_source_ids))
        unexpected = sorted(set(actual_source_ids) - set(expected))
        details = []
        if missing:
            details.append(f"missing={','.join(missing)}")
        if unexpected:
            details.append(f"unexpected={','.join(unexpected)}")
        raise ValueError(
            "Public audit summary must exactly cover the manifest sources"
            + (f" ({'; '.join(details)})" if details else "")
        )
    checked_times = tuple(
        _parse_audit_timestamp(result.checked_at) for result in ordered
    )
    for result in ordered:
        if result.writes_performed:
            raise ValueError("Rule audit public summaries require writes_performed=false")

    overall_status = max(
        (result.status for result in ordered),
        key=_STATUS_PRIORITY.__getitem__,
    )
    status_counts = {
        status.value: sum(result.status is status for result in ordered)
        for status in RuleAuditStatus
    }
    return {
        "schema_version": "1",
        "manifest_version": manifest_version,
        "generated_at": _canonical_utc_timestamp(max(checked_times)),
        "overall_status": overall_status.value,
        "source_count": len(ordered),
        "status_counts": status_counts,
        "writes_performed": False,
        "results": [
            {
                "source_id": result.source_id,
                "title": result.title,
                "rule_version": result.rule_version,
                "effective_date": result.effective_date,
                "checked_at": _canonical_utc_timestamp(checked_times[index]),
                "status": result.status.value,
                "http_status": result.http_status,
                "changed_field_count": len(result.changed_fields),
                "has_errors": bool(result.errors),
                "writes_performed": False,
            }
            for index, result in enumerate(ordered)
        ],
    }


@dataclass(frozen=True, slots=True)
class ApprovedAuditStatus:
    """Human-approved snapshot status rendered by the public UI."""

    schema_version: str
    manifest_version: str
    snapshot_status: str
    last_successful_audit_date: date
    source_count: int
    verified_source_count: int
    writes_performed: bool


def default_approved_status_path() -> Path:
    resource = files("ltc_benefit_agent.audit").joinpath(
        "data", "approved-audit-status-v1.json"
    )
    return Path(str(resource))


def _approved_status_from_mapping(data: Mapping[str, Any]) -> ApprovedAuditStatus:
    required = {
        "schema_version",
        "manifest_version",
        "snapshot_status",
        "last_successful_audit_date",
        "source_count",
        "verified_source_count",
        "writes_performed",
    }
    actual = set(data)
    missing = sorted(required - actual)
    unexpected = sorted(actual - required)
    if missing:
        raise ValueError(
            f"Approved audit status is missing fields: {', '.join(missing)}"
        )
    if unexpected:
        raise ValueError(
            "Approved audit status has unexpected fields: "
            + ", ".join(unexpected)
        )
    if not isinstance(data["writes_performed"], bool):
        raise ValueError("Approved audit status writes_performed must be boolean")
    for field in ("source_count", "verified_source_count"):
        value = data[field]
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(
                f"Approved audit status {field} must be a positive integer"
            )
    return ApprovedAuditStatus(
        schema_version=str(data["schema_version"]),
        manifest_version=str(data["manifest_version"]),
        snapshot_status=str(data["snapshot_status"]),
        last_successful_audit_date=date.fromisoformat(
            str(data["last_successful_audit_date"])
        ),
        source_count=data["source_count"],
        verified_source_count=data["verified_source_count"],
        writes_performed=data["writes_performed"],
    )


def load_approved_audit_status(
    path: str | Path | None = None,
) -> ApprovedAuditStatus:
    """Load and cross-check the packaged, human-approved UI status."""

    status_path = Path(path) if path is not None else default_approved_status_path()
    data = json.loads(status_path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("Approved audit status must be a JSON object")
    status = _approved_status_from_mapping(data)
    manifest = load_manifest()
    if status.schema_version != "1":
        raise ValueError("Unsupported approved audit status schema_version")
    if status.manifest_version != manifest.manifest_version:
        raise ValueError("Approved audit status manifest_version is stale")
    if status.snapshot_status != "APPROVED":
        raise ValueError("Approved audit status must be APPROVED")
    if status.source_count != len(manifest.sources):
        raise ValueError("Approved audit status source_count does not match manifest")
    if status.verified_source_count != status.source_count:
        raise ValueError("Approved audit status must cover every manifest source")
    if status.writes_performed:
        raise ValueError("Approved audit status requires writes_performed=false")
    return status


def render_approved_audit_status_html(
    status: ApprovedAuditStatus | None = None,
) -> str:
    """Render a compact static card without contacting official sources."""

    approved = status or load_approved_audit_status()
    manifest_version = html.escape(approved.manifest_version)
    checked_on = html.escape(approved.last_successful_audit_date.isoformat())
    coverage = f"{approved.verified_source_count}/{approved.source_count}"
    return f"""
<aside class="audit-status-card" aria-label="法規快照稽核狀態">
  <span class="audit-status-dot" aria-hidden="true"></span>
  <div>
    <strong>法規快照 {manifest_version} 已核准</strong>
    <p>最後成功稽核：{checked_on} · {coverage} 官方來源一致</p>
    <small>表示最近一次專案檢查與核准快照一致，不是主管機關保證；對話期間不即時抓取法規。</small>
  </div>
</aside>
""".strip()
