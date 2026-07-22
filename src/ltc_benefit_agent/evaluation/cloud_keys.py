"""雲端診斷用 API key slot；只暴露標籤，不暴露秘密。"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from pydantic import SecretStr

from .evaluator import ScenarioTrace


@dataclass(frozen=True, slots=True)
class CloudApiKeySlot:
    label: str
    api_key: SecretStr = field(repr=False)


def load_cloud_api_key_slots(
    environ: Mapping[str, str] | None = None,
) -> tuple[CloudApiKeySlot, ...]:
    """依主要 key、backup 1–3 載入並去除重複值。"""
    values = environ if environ is not None else os.environ
    primary = values.get("GOOGLE_API_KEY") or values.get("GEMINI_API_KEY")
    candidates = (
        ("primary", primary),
        ("backup_1", values.get("GEMINI_API_KEY_BACKUP")),
        ("backup_2", values.get("GEMINI_API_KEY_BACKUP2")),
        ("backup_3", values.get("GEMINI_API_KEY_BACKUP3")),
    )
    seen: set[bytes] = set()
    slots: list[CloudApiKeySlot] = []
    for label, value in candidates:
        if value is None or not value.strip():
            continue
        fingerprint = hashlib.sha256(value.encode("utf-8")).digest()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        slots.append(CloudApiKeySlot(label=label, api_key=SecretStr(value)))
    return tuple(slots)


def is_quota_or_rate_limit_error(error: str | None) -> bool:
    if not error:
        return False
    normalized = error.upper()
    return "RESOURCE_EXHAUSTED" in normalized or "429" in normalized


def may_failover_without_repeating_progress(trace: ScenarioTrace) -> bool:
    """只允許在 quota 錯誤且尚無任何模型／工具進度時換 key。"""
    return bool(
        is_quota_or_rate_limit_error(trace.error)
        and not trace.turn_outputs
        and not trace.tools
        and trace.pending_preview is None
        and trace.final_report is None
        and not trace.hitl_triggered
    )
