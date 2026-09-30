"""Post-upload parse routing (docstore + parse_pipeline)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatAttachment, HubItem
from app.platform.attachments.kinds import AttachmentKind, classify_attachment
from app.platform.docstore.models import PARSE_READY_STATUSES, ParseStatus
from app.platform.docstore.repository import DocstoreRepository
from app.platform.parse_pipeline.enqueue import enqueue_hub_parse_job, enqueue_parse_job
from app.platform.parse_pipeline.job_builder import (
    build_hub_capture_job_payload,
    new_job_id,
    new_webhook_secret,
)
from app.platform.parse_pipeline.router import PipelineRoute, resolve_pipeline


async def finalize_attachment_parse(
    session: AsyncSession,
    row: ChatAttachment,
    *,
    kind: AttachmentKind,
) -> ChatAttachment:
    resolution = resolve_pipeline(kind)
    docstore = DocstoreRepository(session)

    if resolution.action == PipelineRoute.SKIP.value:
        updated = await docstore.mark_parse_ready(row.id, skipped=True)
        return updated or row

    if resolution.action == PipelineRoute.REJECT.value:
        raise ValueError(f"Unsupported file type for parse: {row.mime_type or row.filename}")

    pipeline_id = resolution.pipeline_id
    assert pipeline_id is not None

    status = str(getattr(row, "parse_status", None) or ParseStatus.READY.value)
    if status in PARSE_READY_STATUSES and row.parse_pipeline_id == pipeline_id:
        return row

    return await enqueue_parse_job(session, row, pipeline_id=pipeline_id)


async def retry_attachment_parse(
    session: AsyncSession,
    row: ChatAttachment,
) -> ChatAttachment:
    """Re-dispatch parse pipeline for a failed or stuck attachment (full job retry)."""
    if row.attachment_role == "transcript_host":
        from app.db.repositories.audio_captures import AudioCaptureRepository
        from app.platform.audio_capture.enqueue import enqueue_capture_parse_job

        capture = await AudioCaptureRepository(session).get_by_host_attachment(row.id)
        if capture is None:
            raise ValueError("Audio capture host attachment has no linked capture")
        return await enqueue_capture_parse_job(session, capture=capture, host_row=row)

    kind = classify_attachment(filename=row.filename, mime_type=row.mime_type)
    resolution = resolve_pipeline(kind)

    if resolution.action == PipelineRoute.SKIP.value:
        docstore = DocstoreRepository(session)
        updated = await docstore.mark_parse_ready(row.id, skipped=True)
        return updated or row

    if resolution.action == PipelineRoute.REJECT.value:
        raise ValueError(f"Unsupported file type for parse: {row.mime_type or row.filename}")

    pipeline_id = resolution.pipeline_id
    assert pipeline_id is not None
    return await enqueue_parse_job(session, row, pipeline_id=pipeline_id)


async def _enqueue_hub_audio_transcription(
    session: AsyncSession,
    row: HubItem,
    *,
    pipeline_id: str,
    parts: list[dict],
    capture_id: uuid.UUID,
    asr_context: str | None = None,
) -> HubItem:
    job_id = new_job_id()
    webhook_secret = new_webhook_secret()
    payload, run_token = build_hub_capture_job_payload(
        row,
        capture_id=capture_id,
        parts=parts,
        pipeline_id=pipeline_id,
        asr_context=asr_context,
        job_id=job_id,
        webhook_secret=webhook_secret,
    )
    return await enqueue_hub_parse_job(
        session,
        row,
        pipeline_id=pipeline_id,
        job_payload=payload,
        run_token=run_token,
    )


async def finalize_hub_item_parse(
    session: AsyncSession,
    row: HubItem,
    *,
    kind: AttachmentKind,
) -> HubItem:
    resolution = resolve_pipeline(kind)
    docstore = DocstoreRepository(session)

    if resolution.action == PipelineRoute.SKIP.value:
        updated = await docstore.mark_parse_ready(row.id, skipped=True)
        return updated or row  # type: ignore[return-value]

    if resolution.action == PipelineRoute.REJECT.value:
        raise ValueError(f"Unsupported file type for parse: {row.mime_type or row.filename}")

    pipeline_id = resolution.pipeline_id
    assert pipeline_id is not None

    status = str(getattr(row, "parse_status", None) or ParseStatus.READY.value)
    if status in PARSE_READY_STATUSES and row.parse_pipeline_id == pipeline_id:
        return row

    if pipeline_id == "audio_transcription_standard":
        if row.item_kind == "audio_capture":
            from app.db.models import HubAudioCapture

            if not row.capture_id:
                raise ValueError("Audio capture hub item has no capture_id")
            capture = await session.get(HubAudioCapture, row.capture_id)
            if capture is None:
                raise ValueError("Audio capture record not found")
            parts = list((capture.context_snapshot or {}).get("parts") or [])
            if not parts:
                raise ValueError("Audio capture has no parts")
            asr_context = (capture.context_snapshot or {}).get("asr_context")
            updated = await _enqueue_hub_audio_transcription(
                session,
                row,
                pipeline_id=pipeline_id,
                parts=parts,
                capture_id=capture.id,
                asr_context=asr_context,
            )
            return updated

        if kind == AttachmentKind.AUDIO:
            parts = [
                {
                    "attachment_id": str(row.id),
                    "filename": row.filename,
                    "mime_type": row.mime_type,
                    "size_bytes": row.size_bytes,
                    "sort_order": 0,
                }
            ]
            updated = await _enqueue_hub_audio_transcription(
                session,
                row,
                pipeline_id=pipeline_id,
                parts=parts,
                capture_id=uuid.uuid4(),
            )
            return updated

    updated = await enqueue_hub_parse_job(session, row, pipeline_id=pipeline_id)
    return updated
