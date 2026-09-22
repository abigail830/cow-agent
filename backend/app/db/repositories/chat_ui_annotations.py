"""Rich UI timeline annotations (viz, artifact, etc.)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatUiAnnotation
from app.db.repositories.transcript_sequence import TranscriptSequenceAllocator


class ChatUiAnnotationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._sequences = TranscriptSequenceAllocator(session)

    async def list_by_chat(self, chat_id: uuid.UUID) -> list[ChatUiAnnotation]:
        result = await self._session.execute(
            select(ChatUiAnnotation)
            .where(ChatUiAnnotation.chat_id == chat_id)
            .order_by(ChatUiAnnotation.sequence)
        )
        return list(result.scalars().all())

    async def list_by_chat_since(self, chat_id: uuid.UUID, min_sequence: int) -> list[ChatUiAnnotation]:
        result = await self._session.execute(
            select(ChatUiAnnotation)
            .where(ChatUiAnnotation.chat_id == chat_id, ChatUiAnnotation.sequence >= min_sequence)
            .order_by(ChatUiAnnotation.sequence)
        )
        return list(result.scalars().all())

    async def insert(
        self,
        *,
        chat_id: uuid.UUID,
        turn_id: uuid.UUID,
        kind: str,
        ref: str,
        display: dict[str, Any] | None = None,
        anchor_message_id: uuid.UUID | None = None,
        annotation_id: uuid.UUID | None = None,
        sequence: int | None = None,
    ) -> ChatUiAnnotation:
        if sequence is None:
            sequence = await self._sequences.allocate(chat_id, 1)
        row = ChatUiAnnotation(
            id=annotation_id or uuid.uuid4(),
            chat_id=chat_id,
            sequence=int(sequence),
            turn_id=turn_id,
            anchor_message_id=anchor_message_id,
            kind=kind,
            ref=ref,
            display=display or {},
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
    ) -> list[ChatUiAnnotation]:
        if not rows:
            return []
        start_sequence = await self._sequences.allocate(chat_id, len(rows))
        saved: list[ChatUiAnnotation] = []
        for index, row in enumerate(rows):
            sequence = row.get("sequence")
            if sequence is None:
                sequence = start_sequence + index
            saved.append(
                await self.insert(
                    chat_id=chat_id,
                    turn_id=row["turn_id"],
                    kind=row["kind"],
                    ref=row["ref"],
                    display=row.get("display"),
                    anchor_message_id=row.get("anchor_message_id"),
                    annotation_id=row.get("id"),
                    sequence=int(sequence),
                )
            )
        if flush:
            await self._session.flush()
        return saved
