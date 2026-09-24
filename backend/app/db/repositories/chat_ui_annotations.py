"""Rich UI timeline annotations (viz, artifact, etc.)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentModel, Chat, ChatUiAnnotation
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

    def _apply_artifact_document_filters(
        self,
        stmt,
        *,
        q: str | None = None,
        agent_id: uuid.UUID | None = None,
        artifact_kind: str | None = None,
    ):
        if q:
            pattern = f"%{q.strip()}%"
            title = ChatUiAnnotation.display["spec"]["title"].astext
            filename = ChatUiAnnotation.display["spec"]["filename"].astext
            stmt = stmt.where(or_(title.ilike(pattern), filename.ilike(pattern)))
        if agent_id is not None:
            stmt = stmt.where(Chat.agent_id == agent_id)
        if artifact_kind:
            kind_col = ChatUiAnnotation.display["spec"]["kind"].astext
            stmt = stmt.where(kind_col == artifact_kind.strip())
        return stmt

    def _artifact_ranked_subquery(
        self,
        user_id: uuid.UUID,
        *,
        q: str | None = None,
        agent_id: uuid.UUID | None = None,
        artifact_kind: str | None = None,
    ):
        row_number = func.row_number().over(
            partition_by=(ChatUiAnnotation.chat_id, ChatUiAnnotation.ref),
            order_by=ChatUiAnnotation.sequence.desc(),
        )
        base = (
            select(
                ChatUiAnnotation.id.label("annotation_id"),
                ChatUiAnnotation.chat_id.label("chat_id"),
                ChatUiAnnotation.ref.label("ref"),
                ChatUiAnnotation.display.label("display"),
                ChatUiAnnotation.created_at.label("created_at"),
                Chat.title.label("chat_title"),
                AgentModel.id.label("agent_id"),
                AgentModel.name.label("agent_name"),
                AgentModel.slug.label("agent_slug"),
                row_number.label("rn"),
            )
            .select_from(ChatUiAnnotation)
            .join(Chat, ChatUiAnnotation.chat_id == Chat.id)
            .join(AgentModel, Chat.agent_id == AgentModel.id)
            .where(Chat.user_id == user_id, ChatUiAnnotation.kind == "artifact")
        )
        base = self._apply_artifact_document_filters(
            base,
            q=q,
            agent_id=agent_id,
            artifact_kind=artifact_kind,
        )
        return base.subquery()

    async def count_artifacts_for_user(
        self,
        user_id: uuid.UUID,
        *,
        q: str | None = None,
        agent_id: uuid.UUID | None = None,
        artifact_kind: str | None = None,
    ) -> int:
        ranked = self._artifact_ranked_subquery(
            user_id,
            q=q,
            agent_id=agent_id,
            artifact_kind=artifact_kind,
        )
        deduped = select(ranked.c.annotation_id).where(ranked.c.rn == 1).subquery()
        result = await self._session.execute(select(func.count()).select_from(deduped))
        return int(result.scalar_one())

    async def list_artifacts_for_user(
        self,
        user_id: uuid.UUID,
        *,
        q: str | None = None,
        agent_id: uuid.UUID | None = None,
        artifact_kind: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        ranked = self._artifact_ranked_subquery(
            user_id,
            q=q,
            agent_id=agent_id,
            artifact_kind=artifact_kind,
        )
        stmt = (
            select(
                ranked.c.annotation_id,
                ranked.c.chat_id,
                ranked.c.ref,
                ranked.c.display,
                ranked.c.created_at,
                ranked.c.chat_title,
                ranked.c.agent_id,
                ranked.c.agent_name,
                ranked.c.agent_slug,
            )
            .where(ranked.c.rn == 1)
            .order_by(ranked.c.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.execute(stmt)
        rows: list[dict[str, Any]] = []
        for row in result.all():
            rows.append(
                {
                    "annotation_id": row.annotation_id,
                    "chat_id": row.chat_id,
                    "ref": row.ref,
                    "display": dict(row.display or {}),
                    "created_at": row.created_at,
                    "chat_title": row.chat_title,
                    "agent_id": row.agent_id,
                    "agent_name": row.agent_name,
                    "agent_slug": row.agent_slug,
                }
            )
        return rows
