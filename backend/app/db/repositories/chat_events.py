"""Append-only chat event store for UI / audit projection."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatEvent


class ChatEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def next_sequence(self, chat_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.coalesce(func.max(ChatEvent.sequence), 0)).where(ChatEvent.chat_id == chat_id)
        )
        return int(result.scalar_one()) + 1

    async def list_by_chat(self, chat_id: uuid.UUID) -> list[ChatEvent]:
        result = await self._session.execute(
            select(ChatEvent).where(ChatEvent.chat_id == chat_id).order_by(ChatEvent.sequence)
        )
        return list(result.scalars().all())

    async def list_by_chat_since(self, chat_id: uuid.UUID, min_sequence: int) -> list[ChatEvent]:
        result = await self._session.execute(
            select(ChatEvent)
            .where(ChatEvent.chat_id == chat_id, ChatEvent.sequence >= min_sequence)
            .order_by(ChatEvent.sequence)
        )
        return list(result.scalars().all())

    async def insert_many(
        self,
        chat_id: uuid.UUID,
        rows: list[dict[str, Any]],
        *,
        flush: bool = True,
    ) -> list[ChatEvent]:
        if not rows:
            return []
        start_sequence = await self.next_sequence(chat_id)
        saved: list[ChatEvent] = []
        for index, row in enumerate(rows):
            sequence = row.get("sequence")
            if sequence is None:
                sequence = start_sequence + index
            event_id = row.get("message_id") or row.get("id") or uuid.uuid4()
            payload = {
                "role": row["role"],
                "message_type": row["message_type"],
                "content": row.get("content"),
                "metadata": row.get("metadata") or {},
                "parent_id": str(row["parent_id"]) if row.get("parent_id") else None,
            }
            event = ChatEvent(
                id=event_id if isinstance(event_id, uuid.UUID) else uuid.UUID(str(event_id)),
                chat_id=chat_id,
                sequence=int(sequence),
                event_type=str(row.get("event_type") or "message"),
                payload=payload,
            )
            self._session.add(event)
            saved.append(event)
        if flush:
            await self._session.flush()
        return saved

    async def get(self, event_id: uuid.UUID) -> ChatEvent | None:
        return await self._session.get(ChatEvent, event_id)

    async def flush(self) -> None:
        await self._session.flush()

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
        event_id: uuid.UUID | None = None,
        event_type: str = "message",
    ) -> ChatEvent:
        if sequence is None:
            sequence = await self.next_sequence(chat_id)
        row = ChatEvent(
            id=event_id or uuid.uuid4(),
            chat_id=chat_id,
            sequence=sequence,
            event_type=event_type,
            payload={
                "role": role,
                "message_type": message_type,
                "content": content,
                "metadata": metadata or {},
                "parent_id": str(parent_id) if parent_id else None,
            },
        )
        self._session.add(row)
        await self._session.flush()
        return row
