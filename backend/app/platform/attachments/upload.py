"""Upload chat attachments — persist a platform blob, then optionally a provider file_id."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chat
from app.db.repositories.attachments import AttachmentRepository
from app.platform.attachments.capabilities import attachment_capabilities
from app.platform.attachments.convert.pdf_pages import count_pdf_pages
from app.platform.attachments.hash import sha256_hex
from app.platform.attachments.kinds import AttachmentKind, classify_attachment
from app.platform.attachments.metadata import attachment_metadata
from app.platform.attachments.pages import attachment_page_cost
from app.platform.attachments.providers.adapters import get_attachment_upload_adapter
from app.platform.attachments.storage import (
    format_inline_provider_file_id,
    save_inline_attachment,
)
from app.platform.attachments.validation import validate_attachment_file, validate_message_attachments
from app.platform.llm.chat_model import resolve_chat_model


class AttachmentUploader:
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
        chat = await self._db.get(Chat, chat_id)
        if chat is None:
            raise ValueError(f"Chat not found: {chat_id}")

        model_entry = await resolve_chat_model(self._db, chat)
        provider = model_entry.provider
        caps = attachment_capabilities(model_id=model_entry.id, provider=provider)
        kind = classify_attachment(filename=filename, mime_type=mime_type)

        page_count: int | None = None
        if kind == AttachmentKind.PDF:
            page_count = count_pdf_pages(data)
        validate_attachment_file(
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
            page_count=page_count,
        )

        content_hash = sha256_hex(data)
        existing = await self._attachments.find_by_content_hash(chat_id, content_hash)
        if existing is not None:
            await self._db.refresh(existing)
            return attachment_metadata(existing)

        attachment_id = uuid.uuid4()
        save_inline_attachment(chat_id, attachment_id, data)
        provider_file_id = format_inline_provider_file_id(attachment_id)

        should_upload = (kind == AttachmentKind.IMAGE and caps.image_file_id) or (
            kind == AttachmentKind.PDF and caps.pdf_file_id
        )
        if should_upload:
            adapter = get_attachment_upload_adapter(provider)
            uploaded = await adapter.upload(filename=filename, mime_type=mime_type, data=data)
            provider_file_id = uploaded.provider_file_id

        row = await self._attachments.insert(
            attachment_id=attachment_id,
            chat_id=chat_id,
            provider=provider,
            provider_file_id=provider_file_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
            content_hash=content_hash,
        )
        await self._db.commit()
        await self._db.refresh(row)
        return attachment_metadata(row)

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
        page_counts = [attachment_page_cost(row, chat_id=chat_id) for row in rows]
        validate_message_attachments(
            size_bytes_list=[row.size_bytes for row in rows],
            page_counts=page_counts,
        )
        return rows
