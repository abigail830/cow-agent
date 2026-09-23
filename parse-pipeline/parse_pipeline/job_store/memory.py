from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from parse_pipeline.job_store.base import JobRecord
from parse_pipeline.schemas.job import JobProgress, JobStatus
from parse_pipeline.schemas.stages import StageId, StageRecord, StageStatus


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class MemoryJobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._idempotency: dict[tuple[str, str], str] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, record: JobRecord) -> JobRecord:
        async with self._lock:
            if record.idempotency_key:
                key = (record.caller_id, record.idempotency_key)
                existing_id = self._idempotency.get(key)
                if existing_id and existing_id in self._jobs:
                    return self._jobs[existing_id]
                self._idempotency[key] = record.job_id
            self._jobs[record.job_id] = record
            return record

    async def get_job(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    async def get_by_idempotency(self, caller_id: str, idempotency_key: str) -> JobRecord | None:
        job_id = self._idempotency.get((caller_id, idempotency_key))
        if not job_id:
            return None
        return self._jobs.get(job_id)

    async def save_job(self, record: JobRecord) -> None:
        async with self._lock:
            self._jobs[record.job_id] = record

    def _find_stage(self, record: JobRecord, stage_id: StageId) -> StageRecord:
        for stage in record.stages:
            if stage.stage_id == stage_id:
                return stage
        raise KeyError(stage_id)

    async def update_stage(
        self,
        job_id: str,
        stage_id: StageId,
        *,
        status: StageStatus,
        outputs: dict[str, Any] | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> JobRecord | None:
        async with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            stage = self._find_stage(record, stage_id)
            stage.status = status
            if outputs is not None:
                stage.outputs = outputs
            if started_at is not None:
                stage.started_at = started_at
            elif status == StageStatus.RUNNING and stage.started_at is None:
                stage.started_at = _utc_now()
            if finished_at is not None:
                stage.finished_at = finished_at
            elif status in {StageStatus.SUCCEEDED, StageStatus.FAILED, StageStatus.SKIPPED}:
                stage.finished_at = _utc_now()
            record.current_stage = stage_id.value
            return record

    async def set_status(
        self,
        job_id: str,
        status: JobStatus,
        *,
        progress: JobProgress | None = None,
    ) -> JobRecord | None:
        async with self._lock:
            record = self._jobs.get(job_id)
            if record is None:
                return None
            record.status = status
            if progress is not None:
                record.progress = progress
            return record
