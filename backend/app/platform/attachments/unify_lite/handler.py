"""Unify-lite attachment handler (stub — upload storage only; extraction TBD)."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.attachments import AttachmentRepository
from app.platform.attachments.attachment_storage import (
    format_inline_provider_file_id,
    save_inline_attachment,
)
from app.platform.attachments.modes import AttachmentProcessingMode
from app.platform.attachments.native.maf_content import attachment_metadata
from app.platform.attachments.validation import validate_attachment_file, validate_message_attachments

UNIFY_LITE_PROVIDER = AttachmentProcessingMode.UNIFY_LITE.value


class UnifyLiteAttachmentHandler:
    """Platform-owned attachment storage; message assembly deferred to unify-lite pipeline."""

    def __init__(self, db: AsyncSession, attachments: AttachmentRepository) -> None:
        self._db = db
        self._attachments = attachments

    async def upload(
        self,
        chat_id: uuid.UUID,
        *,
        filename: str,
        mime_type: str,
        data: bytes,
    ) -> dict:
        validate_attachment_file(filename=filename, mime_type=mime_type, size_bytes=len(data))
        attachment_id = uuid.uuid4()
        save_inline_attachment(chat_id, attachment_id, data)
        row = await self._attachments.insert(
            attachment_id=attachment_id,
            chat_id=chat_id,
            provider=UNIFY_LITE_PROVIDER,
            provider_file_id=format_inline_provider_file_id(attachment_id),
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
        )
        await self._db.commit()
        await self._db.refresh(row)
        return attachment_metadata(row, processing_mode=AttachmentProcessingMode.UNIFY_LITE.value)

    async def resolve_for_message(
        self,
        chat_id: uuid.UUID,
        attachment_ids: list[uuid.UUID],
    ) -> list:
        if not attachment_ids:
            return []
        rows = await self._attachments.list_by_ids(chat_id, attachment_ids)
        if len(rows) != len(set(attachment_ids)):
            raise ValueError("One or more attachments were not found for this chat")
        for row in rows:
            if row.provider != UNIFY_LITE_PROVIDER:
                raise ValueError(
                    f"Attachment {row.filename} was uploaded in native mode; "
                    "switch attachment mode to Native or re-upload in Unify-lite mode."
                )
        validate_message_attachments(size_bytes_list=[row.size_bytes for row in rows])
        return rows

    def ensure_run_input_supported(self) -> None:
        raise ValueError(
            "Unify-lite attachment processing is not available yet. "
            "Switch to Native mode or wait for the upcoming release."
        )
