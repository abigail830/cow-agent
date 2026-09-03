import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatAttachment


class AttachmentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, attachment_id: uuid.UUID) -> ChatAttachment | None:
        return await self._session.get(ChatAttachment, attachment_id)

    async def list_for_chat(self, chat_id: uuid.UUID) -> list[ChatAttachment]:
        result = await self._session.execute(
            select(ChatAttachment)
            .where(ChatAttachment.chat_id == chat_id)
            .order_by(ChatAttachment.created_at)
        )
        return list(result.scalars().all())

    async def list_by_ids(self, chat_id: uuid.UUID, attachment_ids: list[uuid.UUID]) -> list[ChatAttachment]:
        if not attachment_ids:
            return []
        result = await self._session.execute(
            select(ChatAttachment).where(
                ChatAttachment.chat_id == chat_id,
                ChatAttachment.id.in_(attachment_ids),
            )
        )
        rows = list(result.scalars().all())
        order = {aid: idx for idx, aid in enumerate(attachment_ids)}
        rows.sort(key=lambda row: order.get(row.id, len(order)))
        return rows

    async def insert(
        self,
        *,
        chat_id: uuid.UUID,
        provider: str,
        provider_file_id: str,
        filename: str,
        mime_type: str,
        size_bytes: int,
        message_id: uuid.UUID | None = None,
        attachment_id: uuid.UUID | None = None,
    ) -> ChatAttachment:
        row = ChatAttachment(
            id=attachment_id or uuid.uuid4(),
            chat_id=chat_id,
            message_id=message_id,
            provider=provider,
            provider_file_id=provider_file_id,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def link_to_message(self, attachment_ids: list[uuid.UUID], message_id: uuid.UUID) -> None:
        if not attachment_ids:
            return
        result = await self._session.execute(
            select(ChatAttachment).where(ChatAttachment.id.in_(attachment_ids))
        )
        for row in result.scalars().all():
            row.message_id = message_id
