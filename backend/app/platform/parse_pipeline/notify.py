"""Update attachment parse fields in DB (polling clients read via list API)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ChatAttachment


async def notify_attachment_parse_updated(
    session: AsyncSession,
    attachment_id: uuid.UUID,
    *,
    parse_status: str | None = None,
    stage_snapshot: dict[str, Any] | None = None,
) -> None:
    row = await session.get(ChatAttachment, attachment_id)
    if row is None:
        return
    if parse_status is not None:
        row.parse_status = parse_status
    if stage_snapshot is not None:
        row.parse_stage_snapshot = stage_snapshot
    await session.flush()
