from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatDocumentImport


class ChatDocumentImportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_chat(self, chat_id: uuid.UUID) -> list[ChatDocumentImport]:
        result = await self._session.execute(
            select(ChatDocumentImport)
            .where(ChatDocumentImport.chat_id == chat_id)
            .order_by(ChatDocumentImport.sort_order.asc(), ChatDocumentImport.imported_at.asc())
        )
        return list(result.scalars())

    async def get_by_ref(
        self,
        chat_id: uuid.UUID,
        *,
        source: str,
        ref_id: uuid.UUID,
    ) -> ChatDocumentImport | None:
        result = await self._session.execute(
            select(ChatDocumentImport).where(
                ChatDocumentImport.chat_id == chat_id,
                ChatDocumentImport.source == source,
                ChatDocumentImport.ref_id == ref_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(
        self,
        *,
        chat_id: uuid.UUID,
        source: str,
        ref_id: uuid.UUID,
        imported_by_user_id: uuid.UUID,
    ) -> ChatDocumentImport:
        existing = await self.get_by_ref(chat_id, source=source, ref_id=ref_id)
        if existing is not None:
            return existing
        row = ChatDocumentImport(
            id=uuid.uuid4(),
            chat_id=chat_id,
            source=source,
            ref_id=ref_id,
            imported_by_user_id=imported_by_user_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def touch_mentioned(self, row: ChatDocumentImport) -> None:
        row.last_mentioned_at = datetime.now(timezone.utc)
        await self._session.flush()

    async def delete(self, row: ChatDocumentImport) -> None:
        await self._session.delete(row)
        await self._session.flush()
