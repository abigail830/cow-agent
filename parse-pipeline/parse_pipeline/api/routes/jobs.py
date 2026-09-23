from __future__ import annotations

import asyncio
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from parse_pipeline.api.auth import require_service_auth
from parse_pipeline.api.jobs_helpers import record_to_response
from parse_pipeline.job_store.base import JobRecord
from parse_pipeline.job_store.factory import get_job_store
from parse_pipeline.orchestrator.runner import JobRunner
from parse_pipeline.schemas.job import JobResponse, JobStatus, SubmitJobRequest, SubmitJobResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/jobs", tags=["jobs"])


async def _execute_job(job_id: str) -> None:
    runner = JobRunner()
    await runner.run_job(job_id)


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=SubmitJobResponse)
async def create_job(
    body: SubmitJobRequest,
    background_tasks: BackgroundTasks,
    caller_id: str = Depends(require_service_auth),
) -> SubmitJobResponse:
    store = get_job_store()
    if body.idempotency_key:
        existing = await store.get_by_idempotency(caller_id, body.idempotency_key)
        if existing is not None:
            return SubmitJobResponse(job_id=existing.job_id, status=existing.status)

    job_id = f"job_{uuid.uuid4().hex[:26]}"
    record = JobRecord(
        job_id=job_id,
        caller_id=caller_id,
        pipeline_id=str(body.pipeline_id),
        storage_spec=body.storage,
        source=body.source.model_dump(),
        options=body.options.model_dump(),
        callbacks=body.callbacks.model_dump(),
        idempotency_key=body.idempotency_key,
        request_payload=body.model_dump(mode="json"),
    )
    await store.create_job(record)
    background_tasks.add_task(_execute_job, job_id)
    return SubmitJobResponse(job_id=job_id, status=JobStatus.QUEUED)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    caller_id: str = Depends(require_service_auth),
) -> JobResponse:
    store = get_job_store()
    record = await store.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    if record.caller_id != caller_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    return record_to_response(record)


@router.post("/{job_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_job(
    job_id: str,
    caller_id: str = Depends(require_service_auth),
) -> dict[str, str]:
    store = get_job_store()
    record = await store.get_job(job_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    if record.caller_id != caller_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")
    if record.status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}:
        return {"job_id": job_id, "status": record.status.value}
    record.status = JobStatus.CANCELLED
    await store.save_job(record)
    return {"job_id": job_id, "status": JobStatus.CANCELLED.value}
