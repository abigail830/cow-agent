from __future__ import annotations

from typing import Any, Protocol

from parse_pipeline.schemas.job import JobArtifacts, JobError, JobProgress, JobStatus
from parse_pipeline.schemas.stages import StageId, StageRecord, StageStatus


class JobRecord:
    __slots__ = (
        "job_id",
        "caller_id",
        "idempotency_key",
        "pipeline_id",
        "status",
        "storage_spec",
        "source",
        "options",
        "callbacks",
        "provider_id",
        "current_stage",
        "progress",
        "stages",
        "artifacts",
        "error",
        "stats",
        "request_payload",
    )

    def __init__(
        self,
        *,
        job_id: str,
        caller_id: str,
        pipeline_id: str,
        storage_spec: dict[str, Any],
        source: dict[str, Any],
        options: dict[str, Any],
        callbacks: dict[str, Any],
        idempotency_key: str | None = None,
        request_payload: dict[str, Any] | None = None,
    ) -> None:
        from parse_pipeline.schemas.stages import initial_stages

        self.job_id = job_id
        self.caller_id = caller_id
        self.idempotency_key = idempotency_key
        self.pipeline_id = pipeline_id
        self.status = JobStatus.QUEUED
        self.storage_spec = storage_spec
        self.source = source
        self.options = options
        self.callbacks = callbacks
        self.provider_id: str | None = None
        self.current_stage: str | None = None
        self.progress: JobProgress | None = None
        self.stages: list[StageRecord] = initial_stages()
        self.artifacts = JobArtifacts()
        self.error: JobError | None = None
        self.stats: dict[str, Any] | None = None
        self.request_payload = request_payload or {}


class JobStore(Protocol):
    async def create_job(self, record: JobRecord) -> JobRecord: ...

    async def get_job(self, job_id: str) -> JobRecord | None: ...

    async def get_by_idempotency(self, caller_id: str, idempotency_key: str) -> JobRecord | None: ...

    async def save_job(self, record: JobRecord) -> None: ...

    async def update_stage(
        self,
        job_id: str,
        stage_id: StageId,
        *,
        status: StageStatus,
        outputs: dict[str, Any] | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
    ) -> JobRecord | None: ...
