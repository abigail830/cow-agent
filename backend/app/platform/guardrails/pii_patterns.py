"""PII / secret detection patterns for chat-layer redaction (see hooks/chat_redaction.py)."""

from __future__ import annotations

import re
from typing import Callable

# (compiled pattern, replacer) — applied in order to each text block before model calls.
_REDACTION_RULES: tuple[tuple[re.Pattern[str], str | Callable[[re.Match[str]], str]], ...] = (
    (
        re.compile(r"\b(sk-[a-zA-Z0-9_-]{20,})\b"),
        "[REDACTED_API_KEY]",
    ),
    (
        re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
        "[REDACTED_AWS_KEY]",
    ),
    (
        re.compile(r"(?i)(authorization\s*[:=]\s*)([^\s,;\"']+)", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"(?i)(password\s*[:=]\s*)([^\s,;\"']+)", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"(?i)(api[_-]?key\s*[:=]\s*)([^\s,;\"']+)", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"(?i)(secret\s*[:=]\s*)([^\s,;\"']+)", re.IGNORECASE),
        r"\1[REDACTED]",
    ),
    (
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}\b"),
        "Bearer [REDACTED]",
    ),
)


def redact_sensitive_text(text: str) -> tuple[str, int]:
    """Return redacted copy and count of substitutions."""
    if not text:
        return text, 0
    redacted = text
    count = 0
    for pattern, repl in _REDACTION_RULES:
        redacted, n = pattern.subn(repl, redacted)
        count += n
    return redacted, count
