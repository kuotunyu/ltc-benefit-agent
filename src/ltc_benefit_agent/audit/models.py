"""Public data contracts for rule-source manifests and audit results."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping


class RuleAuditStatus(StrEnum):
    """Only the three states allowed by the v0.2 audit contract."""

    VERIFIED_SNAPSHOT = "VERIFIED_SNAPSHOT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    CHECK_UNAVAILABLE = "CHECK_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class ChangedField:
    """One deterministic difference between approved and observed semantics."""

    path: str
    expected: Any
    actual: Any
    impacted_rule_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "expected": self.expected,
            "actual": self.actual,
            "impacted_rule_ids": list(self.impacted_rule_ids),
        }


@dataclass(frozen=True, slots=True)
class RuleSourceManifest:
    """One approved official source and its expected semantic snapshot."""

    schema_version: str
    source_id: str
    title: str
    canonical_url: str
    media_type: str
    rule_version: str
    effective_date: str
    verified_at: str
    raw_sha256: str
    semantic_fingerprint: str
    extractor_id: str
    extractor_version: str
    impacted_rule_ids: tuple[str, ...]
    semantic_snapshot: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class RuleSourceManifestSet:
    """Versioned collection of approved source manifests."""

    schema_version: str
    manifest_version: str
    sources: tuple[RuleSourceManifest, ...]

    def get(self, source_id: str) -> RuleSourceManifest:
        for source in self.sources:
            if source.source_id == source_id:
                return source
        raise KeyError(f"Unknown rule source_id: {source_id}")


@dataclass(frozen=True, slots=True)
class RuleAuditResult:
    """Self-contained evidence from one read-only source check."""

    source_id: str
    title: str
    canonical_url: str
    rule_version: str
    effective_date: str
    checked_at: str
    status: RuleAuditStatus
    fetch_result: str
    http_status: int | None
    raw_sha256_expected: str
    raw_sha256_actual: str | None
    semantic_fingerprint_expected: str
    semantic_fingerprint_actual: str | None
    changed_fields: tuple[ChangedField, ...]
    errors: tuple[str, ...]
    writes_performed: bool = False

    def __post_init__(self) -> None:
        if self.writes_performed:
            raise ValueError("Rule audits must never report writes_performed=true")

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "title": self.title,
            "canonical_url": self.canonical_url,
            "rule_version": self.rule_version,
            "effective_date": self.effective_date,
            "checked_at": self.checked_at,
            "status": self.status.value,
            "fetch_result": self.fetch_result,
            "http_status": self.http_status,
            "raw_sha256_expected": self.raw_sha256_expected,
            "raw_sha256_actual": self.raw_sha256_actual,
            "semantic_fingerprint_expected": self.semantic_fingerprint_expected,
            "semantic_fingerprint_actual": self.semantic_fingerprint_actual,
            "changed_fields": [field.to_dict() for field in self.changed_fields],
            "errors": list(self.errors),
            "writes_performed": self.writes_performed,
        }
