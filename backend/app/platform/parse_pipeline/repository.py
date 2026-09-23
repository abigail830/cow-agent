from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ParseJobEvent, ParseJobRun


class ParseJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_run(
        self,
        *,
        job_id: str,
        attachment_id: uuid.UUID,
        chat_id: uuid.UUID,
        run_token_hash: str,
        webhook_secret: str,
        expires_at: datetime,
        job_payload_json: dict[str, Any],
    ) -> ParseJobRun:
        row = ParseJobRun(
            job_id=job_id,
            attachment_id=attachment_id,
            chat_id=chat_id,
            run_token_hash=run_token_hash,
            webhook_secret=webhook_secret,
            expires_at=expires_at,
            job_payload_json=job_payload_json,
            status="queued",
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def get_run(self, job_id: str) -> ParseJobRun | None:
        return await self._session.get(ParseJobRun, job_id)

    async def get_run_by_token_hash(self, job_id: str, token_hash: str) -> ParseJobRun | None:
        row = await self.get_run(job_id)
        if row is None or row.run_token_hash != token_hash:
            return None
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return None
        return row

    async def record_event(
        self,
        *,
        event_id: str,
        job_id: str,
        attachment_id: uuid.UUID,
        event_type: str,
        payload_json: dict[str, Any],
    ) -> bool:
        existing = await self._session.get(ParseJobEvent, event_id)
        if existing is not None:
            return False
        self._session.add(
            ParseJobEvent(
                event_id=event_id,
                job_id=job_id,
                attachment_id=attachment_id,
                event_type=event_type,
                payload_json=payload_json,
            )
        )
        await self._session.flush()
        return True

    async def update_run_status(self, job_id: str, status: str) -> None:
        row = await self.get_run(job_id)
        if row is None:
            return
        row.status = status
        await self._session.flush()

    async def get_run_for_attachment_token(
        self,
        attachment_id: uuid.UUID,
        token_hash: str,
    ) -> ParseJobRun | None:
        result = await self._session.execute(
            select(ParseJobRun)
            .where(
                ParseJobRun.attachment_id == attachment_id,
                ParseJobRun.run_token_hash == token_hash,
            )
            .order_by(ParseJobRun.created_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < datetime.now(timezone.utc):
            return None
        return row
