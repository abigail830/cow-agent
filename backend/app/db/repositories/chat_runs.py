"""Agent run lifecycle records."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatRun


class ChatRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        chat_id: uuid.UUID,
        run_id: uuid.UUID | None = None,
        user_message_id: uuid.UUID | None = None,
        model_id: str | None = None,
    ) -> ChatRun:
        row = ChatRun(
            id=run_id or uuid.uuid4(),
            chat_id=chat_id,
            user_message_id=user_message_id,
            status="running",
            model_id=model_id,
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get(self, run_id: uuid.UUID) -> ChatRun | None:
        return await self._session.get(ChatRun, run_id)

    async def list_by_chat(self, chat_id: uuid.UUID) -> list[ChatRun]:
        result = await self._session.execute(
            select(ChatRun).where(ChatRun.chat_id == chat_id).order_by(ChatRun.started_at)
        )
        return list(result.scalars().all())

    async def complete(self, run_id: uuid.UUID) -> ChatRun | None:
        return await self._set_status(run_id, status="completed")

    async def cancel(self, run_id: uuid.UUID) -> ChatRun | None:
        return await self._set_status(run_id, status="cancelled")

    async def fail(self, run_id: uuid.UUID, *, error: str | None = None) -> ChatRun | None:
        return await self._set_status(run_id, status="failed", error=error)

    async def link_user_message(self, run_id: uuid.UUID, user_message_id: uuid.UUID) -> ChatRun | None:
        row = await self.get(run_id)
        if row is None:
            return None
        row.user_message_id = user_message_id
        await self._session.flush()
        return row

    async def _set_status(
        self,
        run_id: uuid.UUID,
        *,
        status: str,
        error: str | None = None,
    ) -> ChatRun | None:
        row = await self.get(run_id)
        if row is None:
            return None
        row.status = status
        if error is not None:
            row.error = error
        row.finished_at = datetime.now(timezone.utc)
        await self._session.flush()
        return row
