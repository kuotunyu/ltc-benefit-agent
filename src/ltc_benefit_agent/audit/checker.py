"""Read-only rule-source checker with deterministic three-state outcomes."""

from __future__ import annotations

import hashlib
import socket
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .extractors import (
    ExtractionReviewRequiredError,
    ExtractionUnavailableError,
    extract_semantics,
)
from .manifest import APPROVED_OFFICIAL_URLS, semantic_fingerprint
from .models import (
    ChangedField,
    RuleAuditResult,
    RuleAuditStatus,
    RuleSourceManifest,
)

_MAX_SOURCE_BYTES = 5 * 1024 * 1024
_MISSING = {"state": "MISSING"}


def _checked_at(value: str | None = None) -> str:
    if value is not None:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        return value
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, Mapping):
        flattened: dict[str, Any] = {}
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(_flatten(value[key], path))
        return flattened
    return {prefix: value}


def _semantic_diff(
    expected: Mapping[str, Any],
    actual: Mapping[str, Any],
    impacted_rule_ids: tuple[str, ...],
) -> tuple[ChangedField, ...]:
    expected_flat = _flatten(expected)
    actual_flat = _flatten(actual)
    changed: list[ChangedField] = []
    for path in sorted(set(expected_flat) | set(actual_flat)):
        expected_value = expected_flat.get(path, _MISSING)
        actual_value = actual_flat.get(path, _MISSING)
        if expected_value != actual_value:
            changed.append(
                ChangedField(
                    path=path,
                    expected=expected_value,
                    actual=actual_value,
                    impacted_rule_ids=impacted_rule_ids,
                )
            )
    return tuple(changed)


def _result(
    manifest: RuleSourceManifest,
    *,
    checked_at: str,
    status: RuleAuditStatus,
    fetch_result: str,
    http_status: int | None,
    raw_sha256_actual: str | None,
    semantic_fingerprint_actual: str | None,
    changed_fields: tuple[ChangedField, ...] = (),
    errors: tuple[str, ...] = (),
) -> RuleAuditResult:
    return RuleAuditResult(
        source_id=manifest.source_id,
        title=manifest.title,
        canonical_url=manifest.canonical_url,
        rule_version=manifest.rule_version,
        effective_date=manifest.effective_date,
        checked_at=checked_at,
        status=status,
        fetch_result=fetch_result,
        http_status=http_status,
        raw_sha256_expected=manifest.raw_sha256,
        raw_sha256_actual=raw_sha256_actual,
        semantic_fingerprint_expected=manifest.semantic_fingerprint,
        semantic_fingerprint_actual=semantic_fingerprint_actual,
        changed_fields=changed_fields,
        errors=errors,
        writes_performed=False,
    )


def audit_content(
    manifest: RuleSourceManifest,
    content: bytes,
    *,
    checked_at: str | None = None,
    fetch_result: str = "fixture_success",
    http_status: int | None = None,
    content_type: str | None = None,
) -> RuleAuditResult:
    """Audit supplied bytes without writing a manifest or business rule."""

    timestamp = _checked_at(checked_at)
    raw_sha256 = hashlib.sha256(content).hexdigest()
    if content_type is not None:
        base_content_type = content_type.split(";", maxsplit=1)[0].strip().lower()
        if base_content_type != manifest.media_type:
            return _result(
                manifest,
                checked_at=timestamp,
                status=RuleAuditStatus.CHECK_UNAVAILABLE,
                fetch_result="unexpected_content_type",
                http_status=http_status,
                raw_sha256_actual=raw_sha256,
                semantic_fingerprint_actual=None,
                errors=(
                    f"Expected {manifest.media_type}, received {base_content_type or 'unknown'}",
                ),
            )
    try:
        actual_semantics = extract_semantics(manifest, content)
    except ExtractionReviewRequiredError as exc:
        changed = ChangedField(
            path="extractor.required_structure",
            expected="complete",
            actual="incomplete_or_changed",
            impacted_rule_ids=manifest.impacted_rule_ids,
        )
        return _result(
            manifest,
            checked_at=timestamp,
            status=RuleAuditStatus.REVIEW_REQUIRED,
            fetch_result=fetch_result,
            http_status=http_status,
            raw_sha256_actual=raw_sha256,
            semantic_fingerprint_actual=None,
            changed_fields=(changed,),
            errors=(str(exc),),
        )
    except ExtractionUnavailableError as exc:
        return _result(
            manifest,
            checked_at=timestamp,
            status=RuleAuditStatus.CHECK_UNAVAILABLE,
            fetch_result="format_unreadable",
            http_status=http_status,
            raw_sha256_actual=raw_sha256,
            semantic_fingerprint_actual=None,
            errors=(str(exc),),
        )
    actual_fingerprint = semantic_fingerprint(actual_semantics)
    changed_fields = _semantic_diff(
        manifest.semantic_snapshot,
        actual_semantics,
        manifest.impacted_rule_ids,
    )
    status = (
        RuleAuditStatus.REVIEW_REQUIRED
        if changed_fields
        else RuleAuditStatus.VERIFIED_SNAPSHOT
    )
    return _result(
        manifest,
        checked_at=timestamp,
        status=status,
        fetch_result=fetch_result,
        http_status=http_status,
        raw_sha256_actual=raw_sha256,
        semantic_fingerprint_actual=actual_fingerprint,
        changed_fields=changed_fields,
    )


def unavailable_result(
    manifest: RuleSourceManifest,
    *,
    fetch_result: str,
    error: str,
    checked_at: str | None = None,
    http_status: int | None = None,
) -> RuleAuditResult:
    """Build an explicit CHECK_UNAVAILABLE result for an offline fetch fixture."""

    return _result(
        manifest,
        checked_at=_checked_at(checked_at),
        status=RuleAuditStatus.CHECK_UNAVAILABLE,
        fetch_result=fetch_result,
        http_status=http_status,
        raw_sha256_actual=None,
        semantic_fingerprint_actual=None,
        errors=(error,),
    )


def audit_online(
    manifest: RuleSourceManifest,
    *,
    timeout_seconds: float = 20.0,
    checked_at: str | None = None,
) -> RuleAuditResult:
    """Fetch one allowlisted official source and audit it without rule writes."""

    timestamp = _checked_at(checked_at)
    if APPROVED_OFFICIAL_URLS.get(manifest.source_id) != manifest.canonical_url:
        return unavailable_result(
            manifest,
            checked_at=timestamp,
            fetch_result="url_not_allowlisted",
            error="Canonical URL is not in the approved official allowlist",
        )
    request = Request(
        manifest.canonical_url,
        headers={"User-Agent": "ltc-benefit-agent-rule-audit/0.2"},
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            status = int(response.status)
            final_url = response.geturl()
            content_type = response.headers.get("Content-Type", "")
            content = response.read(_MAX_SOURCE_BYTES + 1)
    except HTTPError as exc:
        return unavailable_result(
            manifest,
            checked_at=timestamp,
            fetch_result="http_error",
            http_status=exc.code,
            error=f"Official source returned HTTP {exc.code}",
        )
    except (URLError, TimeoutError, socket.timeout, OSError) as exc:
        return unavailable_result(
            manifest,
            checked_at=timestamp,
            fetch_result="network_error",
            error=f"Official source could not be fetched: {type(exc).__name__}",
        )
    if final_url != manifest.canonical_url:
        return unavailable_result(
            manifest,
            checked_at=timestamp,
            fetch_result="unexpected_redirect",
            http_status=status,
            error="Official source redirected away from its approved canonical URL",
        )
    if len(content) > _MAX_SOURCE_BYTES:
        return unavailable_result(
            manifest,
            checked_at=timestamp,
            fetch_result="source_too_large",
            http_status=status,
            error=f"Official source exceeds {_MAX_SOURCE_BYTES} bytes",
        )
    return audit_content(
        manifest,
        content,
        checked_at=timestamp,
        fetch_result="success",
        http_status=status,
        content_type=content_type,
    )
