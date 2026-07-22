"""台灣常見 PII 的防禦性遮蔽與最小化稽核紀錄。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from threading import Lock
from typing import Any, Mapping, Sequence

from langchain.agents.middleware import PIIMiddleware


TAIWAN_ID_PATTERN = r"(?i)(?<![A-Z0-9])[A-Z][12]\d{8}(?!\d)"
PHONE_PATTERN = (
    r"(?<!\d)(?:09\d{2}[-\s]?\d{3}[-\s]?\d{3}|"
    r"0[2-8]\d?[-\s]?\d{6,8})(?!\d)"
)
LABELED_NAME_PATTERN = (
    r"(?:姓名|名字(?:是|叫)?|我叫)\s*[:：]?\s*[\u3400-\u9fff]{2,4}"
)

_REDACTION_RULES = (
    (re.compile(TAIWAN_ID_PATTERN), "[REDACTED_TAIWAN_ID]"),
    (re.compile(PHONE_PATTERN), "[REDACTED_PHONE]"),
    (re.compile(LABELED_NAME_PATTERN), "[REDACTED_LABELED_NAME]"),
)


def redact_text(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text 必須是字串")
    redacted = text
    for pattern, replacement in _REDACTION_RULES:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def redact_value(value: Any) -> Any:
    """遞迴遮蔽 model、tool、log 可能接觸的結構。"""

    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): redact_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [redact_value(item) for item in value]
    return value


def build_pii_middleware() -> tuple[PIIMiddleware, ...]:
    common = {
        "strategy": "redact",
        "apply_to_input": True,
        "apply_to_output": True,
        "apply_to_tool_results": True,
    }
    return (
        PIIMiddleware("taiwan_id", detector=TAIWAN_ID_PATTERN, **common),
        PIIMiddleware("phone", detector=PHONE_PATTERN, **common),
        PIIMiddleware("labeled_name", detector=LABELED_NAME_PATTERN, **common),
    )


@dataclass(frozen=True, slots=True)
class AuditEvent:
    timestamp: str
    event: str
    tool_name: str | None
    payload: Any


class SafeAuditLogger:
    """只保留事件與遮蔽後摘要；不保存原始對話。"""

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []
        self._lock = Lock()

    def record(
        self, event: str, *, tool_name: str | None = None, payload: Any = None
    ) -> None:
        item = AuditEvent(
            timestamp=datetime.now(UTC).isoformat(),
            event=event,
            tool_name=tool_name,
            payload=redact_value(payload),
        )
        with self._lock:
            self._events.append(item)

    def snapshot(self) -> tuple[AuditEvent, ...]:
        with self._lock:
            return tuple(self._events)
