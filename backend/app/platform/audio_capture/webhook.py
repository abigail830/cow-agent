"""Sync audio capture + transcript artifact state from parse webhooks."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatUiAnnotation
from app.db.repositories.audio_captures import AudioCaptureRepository
from app.platform.audio_capture.service import artifact_spec
from app.platform.docstore.models import ParseStatus


async def sync_capture_from_parse_webhook(
    session: AsyncSession,
    *,
    attachment_id: uuid.UUID,
    parse_status: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    captures = AudioCaptureRepository(session)
    capture = await captures.get_by_host_attachment(attachment_id)
    if capture is None:
        return

    job_status = "running"
    capture_status = "running"
    if parse_status == ParseStatus.READY.value:
        job_status = "ready"
        capture_status = "ready"
    elif parse_status == ParseStatus.FAILED.value:
        job_status = "failed"
        capture_status = "failed"

    await captures.update_status(
        capture.id,
        status=capture_status,
        error_code=error_code,
        error_message=error_message,
    )

    if not capture.output_annotation_id:
        return
    annotation = await session.get(ChatUiAnnotation, capture.output_annotation_id)
    if annotation is None:
        return

    title = capture.title or "Audio transcript"
    download_url = f"/api/v1/chats/{capture.chat_id}/attachments/{attachment_id}/parsed/content.md"
    spec = artifact_spec(
        capture_id=capture.id,
        host_attachment_id=attachment_id,
        title=title,
        job_status=job_status,
        download_url=download_url if job_status == "ready" else None,
        preview_url=download_url if job_status == "ready" else None,
    )
    annotation.display = _merge_display(annotation.display, spec)


def _merge_display(display: dict[str, Any] | None, spec: dict[str, Any]) -> dict[str, Any]:
    base = dict(display or {})
    base["spec"] = spec
    return base
