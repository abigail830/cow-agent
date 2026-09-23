from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class StageId(StrEnum):
    FETCH = "fetch"
    ANALYZE = "analyze"
    PARSE_SUBMIT = "parse_submit"
    PARSE_WAIT = "parse_wait"
    PARSE_COLLECT = "parse_collect"
    NORMALIZE = "normalize"
    WRITE = "write"
    FINALIZE = "finalize"


STAGE_ORDER: tuple[StageId, ...] = (
    StageId.FETCH,
    StageId.ANALYZE,
    StageId.PARSE_SUBMIT,
    StageId.PARSE_WAIT,
    StageId.PARSE_COLLECT,
    StageId.NORMALIZE,
    StageId.WRITE,
    StageId.FINALIZE,
)


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageRecord(BaseModel):
    stage_id: StageId
    status: StageStatus = StageStatus.PENDING
    started_at: str | None = None
    finished_at: str | None = None
    outputs: dict[str, Any] = Field(default_factory=dict)


def initial_stages() -> list[StageRecord]:
    return [StageRecord(stage_id=s) for s in STAGE_ORDER]
