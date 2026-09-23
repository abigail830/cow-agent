from __future__ import annotations

from parse_pipeline.job_store.base import JobRecord
from parse_pipeline.schemas.job import JobResponse


def record_to_response(record: JobRecord) -> JobResponse:
    return JobResponse(
        job_id=record.job_id,
        status=record.status,
        pipeline_id=record.pipeline_id,
        caller_id=record.caller_id,
        provider_id=record.provider_id,
        current_stage=record.current_stage,
        progress=record.progress,
        stages=record.stages,
        artifacts=record.artifacts,
        error=record.error,
        stats=record.stats,
    )
