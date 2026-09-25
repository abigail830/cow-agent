"""Enqueue parse jobs for audio capture host attachments."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AudioCapture, ChatAttachment
from app.platform.parse_pipeline.enqueue import enqueue_parse_job
from app.platform.parse_pipeline.job_builder import build_capture_job_payload, new_job_id, new_webhook_secret


async def enqueue_capture_parse_job(
    session: AsyncSession,
    *,
    capture: AudioCapture,
    host_row: ChatAttachment,
) -> ChatAttachment:
    parts = list((capture.context_snapshot or {}).get("parts") or [])
    asr_context = (capture.context_snapshot or {}).get("asr_context")
    job_id = new_job_id()
    webhook_secret = new_webhook_secret()
    payload, run_token = build_capture_job_payload(
        host_row,
        capture_id=capture.id,
        parts=parts,
        pipeline_id="audio_transcription_standard",
        asr_context=asr_context,
        job_id=job_id,
        webhook_secret=webhook_secret,
        use_internal_http=True,
    )
    return await enqueue_parse_job(
        session,
        host_row,
        pipeline_id="audio_transcription_standard",
        job_payload=payload,
        run_token=run_token,
    )
