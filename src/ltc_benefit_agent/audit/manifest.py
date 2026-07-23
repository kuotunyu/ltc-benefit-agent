"""Loading and strict validation for versioned official-source manifests."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from importlib.resources import files
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from .models import RuleSourceManifest, RuleSourceManifestSet


APPROVED_OFFICIAL_URLS: Mapping[str, str] = {
    "legacy-2022-regulation": (
        "https://law.moj.gov.tw/LawClass/LawOldVer.aspx?"
        "lnndate=20220120&lser=001&pcode=L0070059"
    ),
    "current-2026-07-regulation": (
        "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=L0070059"
    ),
    "current-care-professional-quota": (
        "https://law.moj.gov.tw/LawClass/LawGetFile.ashx?"
        "FileId=0000398330&lan=C"
    ),
    "current-copay-percentages": (
        "https://law.moj.gov.tw/LawClass/LawGetFile.ashx?"
        "FileId=0000398333&lan=C"
    ),
}

_ALLOWED_RULE_VERSIONS = {"LEGACY_2022", "CURRENT_2026_07"}
_ALLOWED_MEDIA_TYPES = {"text/html", "application/pdf"}
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MANIFEST_FIELDS = {"schema_version", "manifest_version", "sources"}
_SOURCE_FIELDS = {
    "schema_version",
    "source_id",
    "title",
    "canonical_url",
    "media_type",
    "rule_version",
    "effective_date",
    "verified_at",
    "raw_sha256",
    "semantic_fingerprint",
    "extractor_id",
    "extractor_version",
    "impacted_rule_ids",
    "semantic_snapshot",
}


def canonical_json_bytes(value: Any) -> bytes:
    """Encode semantic data with a stable, platform-independent representation."""

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def semantic_fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _require_exact_fields(
    data: Mapping[str, Any],
    expected: set[str],
    *,
    label: str,
) -> None:
    actual = set(data)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing:
        raise ValueError(f"{label} is missing fields: {', '.join(missing)}")
    if unexpected:
        raise ValueError(f"{label} has unexpected fields: {', '.join(unexpected)}")


def _require_nonempty_string(value: Any, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _validate_source(source: RuleSourceManifest) -> None:
    if source.schema_version != "1":
        raise ValueError(f"{source.source_id}: unsupported schema_version")
    approved_url = APPROVED_OFFICIAL_URLS.get(source.source_id)
    if approved_url is None or source.canonical_url != approved_url:
        raise ValueError(f"{source.source_id}: canonical URL is not approved")
    parsed = urlsplit(source.canonical_url)
    if parsed.scheme != "https" or parsed.hostname != "law.moj.gov.tw":
        raise ValueError(f"{source.source_id}: source must use official HTTPS host")
    if source.rule_version not in _ALLOWED_RULE_VERSIONS:
        raise ValueError(f"{source.source_id}: unsupported rule_version")
    if source.media_type not in _ALLOWED_MEDIA_TYPES:
        raise ValueError(f"{source.source_id}: unsupported media_type")
    date.fromisoformat(source.effective_date)
    verified_at = datetime.fromisoformat(source.verified_at.replace("Z", "+00:00"))
    if verified_at.tzinfo is None or verified_at.utcoffset() is None:
        raise ValueError(f"{source.source_id}: verified_at must include a timezone")
    if not _SHA256_RE.fullmatch(source.raw_sha256):
        raise ValueError(f"{source.source_id}: raw_sha256 must be lowercase SHA-256")
    if not _SHA256_RE.fullmatch(source.semantic_fingerprint):
        raise ValueError(
            f"{source.source_id}: semantic_fingerprint must be lowercase SHA-256"
        )
    actual_fingerprint = semantic_fingerprint(source.semantic_snapshot)
    if actual_fingerprint != source.semantic_fingerprint:
        raise ValueError(f"{source.source_id}: semantic_fingerprint does not match")
    if not source.extractor_id or not source.extractor_version:
        raise ValueError(f"{source.source_id}: extractor identity is required")
    if not source.impacted_rule_ids:
        raise ValueError(f"{source.source_id}: impacted_rule_ids cannot be empty")
    if len(source.impacted_rule_ids) != len(set(source.impacted_rule_ids)):
        raise ValueError(f"{source.source_id}: impacted_rule_ids must be unique")


def _source_from_mapping(data: Mapping[str, Any]) -> RuleSourceManifest:
    _require_exact_fields(data, _SOURCE_FIELDS, label="Manifest source")
    impacted_rule_ids = data["impacted_rule_ids"]
    if not isinstance(impacted_rule_ids, list) or not all(
        isinstance(item, str) and item.strip() for item in impacted_rule_ids
    ):
        raise ValueError(
            "Manifest source impacted_rule_ids must be a list of non-empty strings"
        )
    semantic_snapshot = data["semantic_snapshot"]
    if not isinstance(semantic_snapshot, Mapping):
        raise ValueError("Manifest source semantic_snapshot must be an object")
    source = RuleSourceManifest(
        schema_version=_require_nonempty_string(
            data["schema_version"], field="schema_version"
        ),
        source_id=_require_nonempty_string(data["source_id"], field="source_id"),
        title=_require_nonempty_string(data["title"], field="title"),
        canonical_url=_require_nonempty_string(
            data["canonical_url"], field="canonical_url"
        ),
        media_type=_require_nonempty_string(data["media_type"], field="media_type"),
        rule_version=_require_nonempty_string(
            data["rule_version"], field="rule_version"
        ),
        effective_date=_require_nonempty_string(
            data["effective_date"], field="effective_date"
        ),
        verified_at=_require_nonempty_string(
            data["verified_at"], field="verified_at"
        ),
        raw_sha256=_require_nonempty_string(
            data["raw_sha256"], field="raw_sha256"
        ),
        semantic_fingerprint=_require_nonempty_string(
            data["semantic_fingerprint"], field="semantic_fingerprint"
        ),
        extractor_id=_require_nonempty_string(
            data["extractor_id"], field="extractor_id"
        ),
        extractor_version=_require_nonempty_string(
            data["extractor_version"], field="extractor_version"
        ),
        impacted_rule_ids=tuple(impacted_rule_ids),
        semantic_snapshot=semantic_snapshot,
    )
    _validate_source(source)
    return source


def default_manifest_path() -> Path:
    resource = files("ltc_benefit_agent.audit").joinpath(
        "data", "rule-sources-v1.json"
    )
    return Path(str(resource))


def load_manifest(path: str | Path | None = None) -> RuleSourceManifestSet:
    """Load the packaged manifest or an explicitly supplied local manifest."""

    manifest_path = Path(path) if path is not None else default_manifest_path()
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(data, Mapping):
        raise ValueError("Manifest must be a JSON object")
    _require_exact_fields(data, _MANIFEST_FIELDS, label="Manifest")
    if data.get("schema_version") != "1":
        raise ValueError("Unsupported manifest schema_version")
    manifest_version = _require_nonempty_string(
        data["manifest_version"], field="manifest_version"
    )
    if not isinstance(data["sources"], list):
        raise ValueError("Manifest sources must be a list")
    if not all(isinstance(item, Mapping) for item in data["sources"]):
        raise ValueError("Every manifest source must be an object")
    sources = tuple(_source_from_mapping(item) for item in data["sources"])
    if not sources:
        raise ValueError("Manifest must contain at least one source")
    source_ids = [source.source_id for source in sources]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Manifest source_id values must be unique")
    if set(source_ids) != set(APPROVED_OFFICIAL_URLS):
        raise ValueError("Manifest must exactly cover the approved official sources")
    return RuleSourceManifestSet(
        schema_version="1",
        manifest_version=manifest_version,
        sources=sources,
    )
