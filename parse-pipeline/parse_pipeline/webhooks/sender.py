from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from typing import Any

import httpx

from parse_pipeline.config import get_settings
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

    settings = get_settings()
    max_retries = max(0, int(settings.webhook_max_retries))
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=settings.webhook_timeout_sec) as client:
                response = await client.post(url, content=body, headers=headers)
                response.raise_for_status()
            return
        except Exception as exc:
            last_exc = exc
            if attempt < max_retries:
                delay = min(2.0, 0.5 * (attempt + 1))
                logger.warning(
                    "webhook delivery retry job_id=%s event=%s attempt=%s/%s",
                    record.job_id,
                    event_type,
                    attempt + 1,
                    max_retries,
                )
                await asyncio.sleep(delay)
                continue
            logger.exception(
                "webhook delivery failed job_id=%s event=%s after %s retries",
                record.job_id,
                event_type,
                max_retries,
            )
    if last_exc is not None:
        del last_exc


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
