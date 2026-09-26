"""Sync audio capture + transcript artifact state from parse webhooks."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatUiAnnotation
from app.db.repositories.audio_captures import AudioCaptureRepository
from app.platform.audio_capture.service import artifact_spec
from app.platform.docstore.manifest import parsed_artifact_in_manifest
from app.platform.docstore.models import ParseStatus
from app.platform.docstore.repository import DocstoreRepository


def _capture_job_status(parse_status: str) -> tuple[str, str]:
    if parse_status == ParseStatus.FAILED.value:
        return "failed", "failed"
    if parse_status == ParseStatus.READY.value:
        return "ready", "ready"
    return "running", "running"


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

    capture_status, job_status = _capture_job_status(parse_status)

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
    download_url = f"/api/v1/chats/{capture.chat_id}/attachments/{attachment_id}/parsed/content_md"
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


async def maybe_finalize_capture_after_parsed_artifact(
    session: AsyncSession,
    *,
    attachment_id: uuid.UUID,
    artifact_key: str,
) -> None:
    """When transcript markdown + meta are stored, mark capture ready even if webhook raced."""
    if artifact_key not in {"content_md", "meta_json"}:
        return

    from app.db.models import ChatAttachment

    attachment = await session.get(ChatAttachment, attachment_id)
    if attachment is None or attachment.attachment_role != "transcript_host":
        return

    manifest = attachment.parsed_artifact_manifest
    if not parsed_artifact_in_manifest(manifest, "content_md"):
        return
    if not parsed_artifact_in_manifest(manifest, "meta_json"):
        return

    docstore = DocstoreRepository(session)
    await docstore.apply_parse_webhook(
        attachment_id,
        status=ParseStatus.READY.value,
        stage_snapshot={
            "current_stage": "finalize",
            "message": "Transcript ready",
            "stages": [],
        },
    )
    await sync_capture_from_parse_webhook(
        session,
        attachment_id=attachment_id,
        parse_status=ParseStatus.READY.value,
    )
