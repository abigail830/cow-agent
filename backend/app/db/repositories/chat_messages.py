"""Append-only MAF message store."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatMessage
from app.db.repositories.transcript_sequence import TranscriptSequenceAllocator
from app.platform.memory.message_validate import (
    assert_no_tool_calls_in_partial_assistant,
    maf_message_id_from_body,
    validate_message_body,
)


class ChatMessageRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._sequences = TranscriptSequenceAllocator(session)

    async def list_by_chat(self, chat_id: uuid.UUID, *, tail: int | None = None) -> list[ChatMessage]:
        if tail is not None and tail > 0:
            result = await self._session.execute(
                select(ChatMessage)
                .where(ChatMessage.chat_id == chat_id)
                .order_by(ChatMessage.sequence.desc())
                .limit(tail)
            )
            return list(reversed(result.scalars().all()))
        result = await self._session.execute(
            select(ChatMessage).where(ChatMessage.chat_id == chat_id).order_by(ChatMessage.sequence)
        )
        return list(result.scalars().all())

    async def list_by_chat_since(self, chat_id: uuid.UUID, min_sequence: int) -> list[ChatMessage]:
        result = await self._session.execute(
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id, ChatMessage.sequence >= min_sequence)
            .order_by(ChatMessage.sequence)
        )
        return list(result.scalars().all())

    async def list_by_turn(self, chat_id: uuid.UUID, turn_id: uuid.UUID) -> list[ChatMessage]:
        result = await self._session.execute(
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id, ChatMessage.turn_id == turn_id)
            .order_by(ChatMessage.sequence)
        )
        return list(result.scalars().all())

    async def list_user_messages_by_chat(self, chat_id: uuid.UUID) -> list[ChatMessage]:
        result = await self._session.execute(
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id, ChatMessage.role == "user")
            .order_by(ChatMessage.sequence)
        )
        return list(result.scalars().all())

    async def get(self, message_id: uuid.UUID) -> ChatMessage | None:
        return await self._session.get(ChatMessage, message_id)

    async def insert(
        self,
        *,
        chat_id: uuid.UUID,
        turn_id: uuid.UUID,
        body: dict[str, Any],
        run_id: uuid.UUID | None = None,
        message_id: uuid.UUID | None = None,
        sequence: int | None = None,
    ) -> ChatMessage:
        validated = validate_message_body(body)
        assert_no_tool_calls_in_partial_assistant(validated)
        role = str(validated.get("role") or "").strip()
        if sequence is None:
            sequence = await self._sequences.allocate(chat_id, 1)
        row = ChatMessage(
            id=message_id or uuid.uuid4(),
            chat_id=chat_id,
            sequence=int(sequence),
            turn_id=turn_id,
            run_id=run_id,
            role=role,
            maf_message_id=maf_message_id_from_body(validated),
            body=validated,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def insert_many(
        self,
        chat_id: uuid.UUID,
        rows: list[dict[str, Any]],
        *,
        flush: bool = True,
    ) -> list[ChatMessage]:
        if not rows:
            return []
        missing_count = sum(1 for row in rows if row.get("sequence") is None)
        start_sequence = (
            await self._sequences.allocate(chat_id, missing_count) if missing_count else 0
        )
        saved: list[ChatMessage] = []
        alloc_index = 0
        for row in rows:
            sequence = row.get("sequence")
            if sequence is None:
                sequence = start_sequence + alloc_index
                alloc_index += 1
            saved.append(
                await self.insert(
                    chat_id=chat_id,
                    turn_id=row["turn_id"],
                    body=row["body"],
                    run_id=row.get("run_id"),
                    message_id=row.get("id"),
                    sequence=int(sequence),
                )
            )
        if flush:
            await self._session.flush()
        return saved

    async def update_body(self, message_id: uuid.UUID, body: dict[str, Any]) -> ChatMessage:
        row = await self.get(message_id)
        if row is None:
            raise ValueError(f"ChatMessage {message_id} not found")
        validated = validate_message_body(body)
        assert_no_tool_calls_in_partial_assistant(validated)
        row.body = validated
        row.role = str(validated.get("role") or "").strip()
        row.maf_message_id = maf_message_id_from_body(validated)
        await self._session.flush()
        return row

    async def flush(self) -> None:
        await self._session.flush()
