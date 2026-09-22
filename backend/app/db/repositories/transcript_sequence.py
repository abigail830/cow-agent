"""Atomic sequence allocation for chat transcript timeline."""

from __future__ import annotations

import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chat


class TranscriptSequenceAllocator:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def allocate(self, chat_id: uuid.UUID, count: int = 1) -> int:
        if count < 1:
            raise ValueError("count must be >= 1")
        result = await self._session.execute(
            update(Chat)
            .where(Chat.id == chat_id)
            .values(transcript_seq=Chat.transcript_seq + count)
            .returning(Chat.transcript_seq)
        )
        end_seq = result.scalar_one_or_none()
        if end_seq is None:
            raise ValueError(f"Chat not found: {chat_id}")
        return int(end_seq) - count + 1

    async def ensure_chat(self, chat_id: uuid.UUID) -> None:
        result = await self._session.execute(select(Chat.id).where(Chat.id == chat_id))
        if result.scalar_one_or_none() is None:
            raise ValueError(f"Chat not found: {chat_id}")
