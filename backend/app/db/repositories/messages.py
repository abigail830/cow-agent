import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Message


class MessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_sequence(self, chat_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(Message.sequence), 0)).where(Message.chat_id == chat_id)
        )
        current = result.scalar_one()
        return int(current) + 1

    async def list_by_chat(self, chat_id: uuid.UUID) -> list[Message]:
        result = await self._session.execute(
            select(Message).where(Message.chat_id == chat_id).order_by(Message.sequence)
        )
        return list(result.scalars().all())

    async def insert(
        self,
        *,
        chat_id: uuid.UUID,
        role: str,
        message_type: str,
        content: str | None,
        sequence: int | None = None,
        metadata: dict[str, Any] | None = None,
        parent_id: uuid.UUID | None = None,
        message_id: uuid.UUID | None = None,
    ) -> Message:
        if sequence is None:
            sequence = await self.next_sequence(chat_id)
        row = Message(
            id=message_id or uuid.uuid4(),
            chat_id=chat_id,
            role=role,
            content=content,
            message_type=message_type,
            message_metadata=metadata or {},
            parent_id=parent_id,
            sequence=sequence,
        )
        self._session.add(row)
        await self._session.flush()
        return row
