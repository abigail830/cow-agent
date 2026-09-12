"""Native attachment upload — provider Files API or inline vision storage."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import Chat
from app.db.repositories.attachments import AttachmentRepository
from app.platform.llm.chat_model import resolve_chat_model
from app.platform.attachments.attachment_storage import (
    format_inline_provider_file_id,
    save_inline_attachment,
)
from app.platform.attachments.modes import AttachmentProcessingMode
from app.platform.attachments.native.adapters import (
    get_attachment_upload_adapter,
    should_use_azure_inline_image,
)
from app.platform.attachments.native.maf_content import attachment_metadata
from app.platform.attachments.validation import validate_attachment_file, validate_message_attachments
from app.platform.llm.model_registry import ModelProvider


class NativeAttachmentUploader:
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
        model_provider = model_entry.provider

        validate_attachment_file(filename=filename, mime_type=mime_type, size_bytes=len(data))

        settings = get_settings()
        if (
            model_provider == ModelProvider.AZURE_OPENAI.value
            and should_use_azure_inline_image(
                base_url=settings.azure_openai_base_url,
                mime_type=mime_type,
            )
        ):
            return await self._upload_inline_image(
                chat_id=chat_id,
                filename=filename,
                mime_type=mime_type,
                data=data,
                provider=ModelProvider.AZURE_OPENAI.value,
            )

        if model_provider in {
            ModelProvider.SILICONFLOW.value,
            ModelProvider.DASHSCOPE.value,
            ModelProvider.DEEPSEEK.value,
        }:
            if not mime_type.startswith("image/"):
                raise ValueError(
                    "This model provider only supports image attachments (inline); "
                    "PDF and other files are not supported yet."
                )
            return await self._upload_inline_image(
                chat_id=chat_id,
                filename=filename,
                mime_type=mime_type,
                data=data,
                provider=model_provider,
            )

        adapter = get_attachment_upload_adapter(model_provider)
        uploaded = await adapter.upload(filename=filename, mime_type=mime_type, data=data)

        row = await self._attachments.insert(
            chat_id=chat_id,
            provider=uploaded.provider,
            provider_file_id=uploaded.provider_file_id,
            filename=uploaded.filename,
            mime_type=uploaded.mime_type,
            size_bytes=uploaded.size_bytes,
        )
        await self._db.commit()
        await self._db.refresh(row)
        return attachment_metadata(row, processing_mode=AttachmentProcessingMode.NATIVE.value)

    async def _upload_inline_image(
        self,
        chat_id: uuid.UUID,
        *,
        filename: str,
        mime_type: str,
        data: bytes,
        provider: str,
    ) -> dict:
        attachment_id = uuid.uuid4()
        save_inline_attachment(chat_id, attachment_id, data)
        row = await self._attachments.insert(
            attachment_id=attachment_id,
            chat_id=chat_id,
            provider=provider,
            provider_file_id=format_inline_provider_file_id(attachment_id),
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
        )
        await self._db.commit()
        await self._db.refresh(row)
        return attachment_metadata(row, processing_mode=AttachmentProcessingMode.NATIVE.value)

    async def resolve_for_message(
        self,
        chat_id: uuid.UUID,
        attachment_ids: list[uuid.UUID],
        *,
        expected_provider: str,
    ) -> list:
        if not attachment_ids:
            return []
        rows = await self._attachments.list_by_ids(chat_id, attachment_ids)
        if len(rows) != len(set(attachment_ids)):
            raise ValueError("One or more attachments were not found for this chat")
        for row in rows:
            if row.provider == AttachmentProcessingMode.UNIFY_LITE.value:
                raise ValueError(
                    f"Attachment {row.filename} was uploaded in unify-lite mode; "
                    "switch attachment mode to Unify-lite or re-upload in Native mode."
                )
            if row.provider != expected_provider:
                raise ValueError(
                    f"Attachment {row.filename} was uploaded for {row.provider} "
                    f"but this agent uses {expected_provider}. Please re-upload."
                )
        validate_message_attachments(size_bytes_list=[row.size_bytes for row in rows])
        return rows
