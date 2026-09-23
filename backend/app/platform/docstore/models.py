from __future__ import annotations

from enum import StrEnum


class ParseStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    READY = "ready"
    FAILED = "failed"
    SKIPPED = "skipped"


PARSE_READY_STATUSES = frozenset({ParseStatus.READY.value, ParseStatus.SKIPPED.value})
