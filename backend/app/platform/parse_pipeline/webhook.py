from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.docstore.models import ParseStatus
from app.platform.docstore.repository import DocstoreRepository
from app.platform.parse_pipeline.events import publish_attachment_parse_updated
from app.platform.parse_pipeline.repository import ParseJobRepository

logger = logging.getLogger(__name__)

_WEBHOOK_MAX_SKEW_SEC = 300


def verify_webhook_signature(
    *,
    secret: str,
    timestamp: str,
    body: bytes,
    signature_header: str | None,
) -> bool:
    if not signature_header or not signature_header.startswith("v1="):
        return False
    try:
        ts = int(timestamp)
    except ValueError:
        return False
    if abs(int(time.time()) - ts) > _WEBHOOK_MAX_SKEW_SEC:
        return False
    expected = hmac.new(
        secret.encode(),
        f"{timestamp}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()
    provided = signature_header.removeprefix("v1=")
    return hmac.compare_digest(expected, provided)


def _stage_snapshot_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    progress = payload.get("progress") or {}
    stages = payload.get("stages") or []
    simplified = [
        {
            "stage_id": s.get("stage_id"),
            "status": s.get("status"),
            "started_at": s.get("started_at"),
            "finished_at": s.get("finished_at"),
        }
        for s in stages
        if isinstance(s, dict)
    ]
    return {
        "current_stage": payload.get("current_stage"),
        "message": progress.get("message") if isinstance(progress, dict) else None,
        "stages": simplified,
    }


def _map_parse_status(payload: dict[str, Any]) -> str:
    event = payload.get("event") or ""
    status = str(payload.get("status") or "").lower()
    artifacts = payload.get("artifacts") or {}
    if event == "job.failed" or status == "failed":
        return ParseStatus.FAILED.value
    if event == "job.completed" or status == "succeeded":
        if isinstance(artifacts, dict) and artifacts.get("ready"):
            return ParseStatus.READY.value
        return ParseStatus.RUNNING.value
    if status in {"running", "queued"}:
        return ParseStatus.RUNNING.value
    return ParseStatus.RUNNING.value


async def apply_webhook_event(
    session: AsyncSession,
    *,
    event_id: str,
    body: bytes,
    run_row,
) -> dict[str, Any] | None:
    payload = json.loads(body.decode("utf-8"))
    job_id = str(payload.get("job_id") or run_row.job_id)
    event_type = str(payload.get("event") or "stage.updated")

    jobs = ParseJobRepository(session)
    if not await jobs.record_event(
        event_id=event_id,
        job_id=job_id,
        attachment_id=run_row.attachment_id,
        event_type=event_type,
        payload_json=payload,
    ):
        return None

    parse_status = _map_parse_status(payload)

    error = payload.get("error") or {}
    error_code = error.get("code") if isinstance(error, dict) else None
    error_message = error.get("message") if isinstance(error, dict) else None

    snapshot = _stage_snapshot_from_payload(payload)
    docstore = DocstoreRepository(session)
    row = await docstore.apply_parse_webhook(
        run_row.attachment_id,
        status=parse_status,
        stage_snapshot=snapshot,
        error_code=str(error_code) if error_code else None,
        error_message=str(error_message) if error_message else None,
    )
    await jobs.update_run_status(job_id, str(payload.get("status") or run_row.status))

    if row is None:
        return None

    out = {
        "attachment_id": str(row.id),
        "chat_id": str(row.chat_id),
        "parse_status": row.parse_status,
        "parse_pipeline_id": row.parse_pipeline_id,
        "parse_job_id": row.parse_job_id,
        "parse_error_message": row.parse_error_message,
        "parse_progress": snapshot,
    }
    from app.platform.audio_capture.webhook import sync_capture_from_parse_webhook

    await sync_capture_from_parse_webhook(
        session,
        attachment_id=run_row.attachment_id,
        parse_status=parse_status,
        error_code=str(error_code) if error_code else None,
        error_message=str(error_message) if error_message else None,
    )

    publish_attachment_parse_updated(str(row.chat_id), out)
    return out
