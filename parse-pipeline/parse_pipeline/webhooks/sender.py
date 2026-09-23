from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Any

import httpx

from parse_pipeline.job_store.base import JobRecord
from parse_pipeline.schemas.job import JobStatus

logger = logging.getLogger(__name__)

_sequence = 0


def _next_sequence() -> int:
    global _sequence
    _sequence += 1
    return _sequence


def _sign(secret: str, timestamp: str, body: bytes) -> str:
    payload = f"{timestamp}.".encode() + body
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"v1={digest}"


def _job_payload(record: JobRecord, event_type: str) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "event": event_type,
        "job_id": record.job_id,
        "status": record.status.value,
        "pipeline_id": record.pipeline_id,
        "provider_id": record.provider_id,
        "current_stage": record.current_stage,
        "progress": record.progress.model_dump() if record.progress else None,
        "stages": [s.model_dump(mode="json") for s in record.stages],
        "artifacts": record.artifacts.model_dump(),
        "error": record.error.model_dump() if record.error else None,
        "stats": record.stats,
    }


async def emit_event(record: JobRecord, event_type: str) -> None:
    callbacks = record.callbacks or {}
    url = callbacks.get("webhook_url")
    secret = callbacks.get("webhook_secret")
    events = callbacks.get("events") or []
    if not url or not secret:
        return
    if events and event_type not in events:
        return

    body_dict = _job_payload(record, event_type)
    body = json.dumps(body_dict, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(time.time()))
    headers = {
        "Content-Type": "application/json",
        "X-Parse-Webhook-Id": str(uuid.uuid4()),
        "X-Parse-Timestamp": timestamp,
        "X-Parse-Sequence": str(_next_sequence()),
        "X-Parse-Signature": _sign(secret, timestamp, body),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, content=body, headers=headers)
            response.raise_for_status()
    except Exception:
        logger.exception("webhook delivery failed job_id=%s event=%s", record.job_id, event_type)


async def emit_stage_updated(record: JobRecord) -> None:
    await emit_event(record, "stage.updated")


async def emit_job_completed(record: JobRecord) -> None:
    await emit_event(record, "job.completed")


async def emit_job_failed(record: JobRecord) -> None:
    await emit_event(record, "job.failed")


def status_event(status: JobStatus) -> str:
    if status == JobStatus.SUCCEEDED:
        return "job.completed"
    if status == JobStatus.FAILED:
        return "job.failed"
    return "stage.updated"
