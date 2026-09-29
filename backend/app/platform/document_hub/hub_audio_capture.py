"""Multi-part audio capture uploads for Document Hub."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HubAudioCapture, HubItem
from app.db.repositories.hub_items import HubItemRepository
from app.platform.attachments.hash import sha256_hex
from app.platform.attachments.kinds import AttachmentKind, classify_attachment
from app.platform.attachments.validation import validate_attachment_file
from app.platform.document_hub.storage import format_hub_inline_provider_file_id, save_hub_original
from app.platform.parse_pipeline.enqueue import enqueue_hub_parse_job
from app.platform.parse_pipeline.job_builder import build_hub_capture_job_payload, new_job_id, new_webhook_secret


async def create_hub_audio_capture(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    folder_id: uuid.UUID,
    title: str | None,
    parts: list[tuple[str, str, bytes]],
) -> HubItem:
    if not parts:
        raise ValueError("At least one audio file is required")

    items = HubItemRepository(session)
    host_id = uuid.uuid4()
    host_filename = f"{(title or 'Audio transcript').strip()}.md"
    host_row = await items.insert(
        item_id=host_id,
        user_id=user_id,
        folder_id=folder_id,
        item_kind="audio_capture",
        filename=host_filename,
        mime_type="text/markdown",
        size_bytes=0,
        content_hash=None,
        provider="inline",
        provider_file_id=format_hub_inline_provider_file_id(host_id),
        attachment_role="transcript_host",
    )

    capture = HubAudioCapture(
        id=uuid.uuid4(),
        user_id=user_id,
        folder_id=folder_id,
        host_item_id=host_id,
        title=title,
        status="pending",
        context_snapshot={"parts": []},
    )
    session.add(capture)
    await session.flush()

    host_row.capture_id = capture.id
    part_specs: list[dict] = []
    sort_order = 0
    for filename, mime_type, data in parts:
        kind = classify_attachment(filename=filename, mime_type=mime_type)
        if kind != AttachmentKind.AUDIO:
            raise ValueError(f"Not an audio file: {filename}")
        validate_attachment_file(filename=filename, mime_type=mime_type, size_bytes=len(data))
        part_id = uuid.uuid4()
        save_hub_original(user_id, part_id, data)
        await items.insert(
            item_id=part_id,
            user_id=user_id,
            folder_id=folder_id,
            item_kind="file",
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
            content_hash=sha256_hex(data),
            provider="inline",
            provider_file_id=format_hub_inline_provider_file_id(part_id),
            attachment_role="audio_part",
            capture_id=capture.id,
            sort_order=sort_order,
        )
        part_specs.append(
            {
                "attachment_id": str(part_id),
                "filename": filename,
                "mime_type": mime_type,
                "size_bytes": len(data),
                "sort_order": sort_order,
            }
        )
        sort_order += 1

    capture.context_snapshot = {"parts": part_specs, "asr_context": None}
    await session.flush()

    job_id = new_job_id()
    webhook_secret = new_webhook_secret()
    payload, run_token = build_hub_capture_job_payload(
        host_row,
        capture_id=capture.id,
        parts=part_specs,
        pipeline_id="audio_transcription_standard",
        asr_context=None,
        job_id=job_id,
        webhook_secret=webhook_secret,
    )

    await enqueue_hub_parse_job(
        session,
        host_row,
        pipeline_id="audio_transcription_standard",
        job_payload=payload,
        run_token=run_token,
    )
    capture.parse_job_id = host_row.parse_job_id
    capture.status = "running"
    await session.flush()
    return host_row
