import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import AgentModel, Chat
from app.db.repositories.attachments import AttachmentRepository
from app.platform.attachment_adapters import (
    attachment_metadata,
    get_attachment_upload_adapter,
    should_use_azure_inline_image,
    validate_attachment_file,
    validate_message_attachments,
)
from app.platform.attachment_storage import (
    format_inline_provider_file_id,
    save_inline_attachment,
)
from app.platform.model_registry import ModelProvider


class AttachmentService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._attachments = AttachmentRepository(db)

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

        agent = await self._db.get(AgentModel, chat.agent_id)
        if agent is None:
            raise ValueError("Agent not found for chat")

        validate_attachment_file(filename=filename, mime_type=mime_type, size_bytes=len(data))

        settings = get_settings()
        if (
            agent.model_provider == ModelProvider.AZURE_OPENAI.value
            and should_use_azure_inline_image(
                base_url=settings.azure_openai_base_url,
                mime_type=mime_type,
            )
        ):
            return await self._upload_azure_inline_image(
                chat_id=chat_id,
                filename=filename,
                mime_type=mime_type,
                data=data,
            )

        adapter = get_attachment_upload_adapter(agent.model_provider)
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
        return attachment_metadata(row)

    async def _upload_azure_inline_image(
        self,
        chat_id: uuid.UUID,
        *,
        filename: str,
        mime_type: str,
        data: bytes,
    ) -> dict:
        attachment_id = uuid.uuid4()
        save_inline_attachment(chat_id, attachment_id, data)
        row = await self._attachments.insert(
            attachment_id=attachment_id,
            chat_id=chat_id,
            provider=ModelProvider.AZURE_OPENAI.value,
            provider_file_id=format_inline_provider_file_id(attachment_id),
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
        )
        await self._db.commit()
        await self._db.refresh(row)
        return attachment_metadata(row)

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
            if row.provider != expected_provider:
                raise ValueError(
                    f"Attachment {row.filename} was uploaded for {row.provider} "
                    f"but this agent uses {expected_provider}. Please re-upload."
                )
        validate_message_attachments(size_bytes_list=[row.size_bytes for row in rows])
        return rows
