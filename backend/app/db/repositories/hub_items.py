from __future__ import annotations

import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HubItem


class HubItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_owned(self, user_id: uuid.UUID, item_id: uuid.UUID) -> HubItem | None:
        row = await self._session.get(HubItem, item_id)
        if row is None or row.user_id != user_id:
            return None
        return row

    async def get(self, item_id: uuid.UUID) -> HubItem | None:
        return await self._session.get(HubItem, item_id)

    async def list_folder_items(
        self,
        user_id: uuid.UUID,
        folder_id: uuid.UUID,
        *,
        q: str | None = None,
    ) -> list[HubItem]:
        stmt = (
            select(HubItem)
            .where(
                HubItem.user_id == user_id,
                HubItem.folder_id == folder_id,
                or_(HubItem.attachment_role.is_(None), HubItem.attachment_role != "audio_part"),
            )
            .order_by(HubItem.updated_at.desc())
        )
        if q and q.strip():
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(HubItem.filename.ilike(pattern))
        result = await self._session.execute(stmt)
        return list(result.scalars())

    async def find_by_content_hash(self, user_id: uuid.UUID, content_hash: str) -> HubItem | None:
        if not content_hash:
            return None
        result = await self._session.execute(
            select(HubItem)
            .where(
                HubItem.user_id == user_id,
                HubItem.content_hash == content_hash,
                or_(HubItem.attachment_role.is_(None), HubItem.attachment_role != "audio_part"),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def insert(
        self,
        *,
        item_id: uuid.UUID | None = None,
        user_id: uuid.UUID,
        folder_id: uuid.UUID,
        item_kind: str,
        filename: str,
        mime_type: str,
        size_bytes: int,
        content_hash: str | None,
        provider: str,
        provider_file_id: str,
        attachment_role: str | None = None,
        capture_id: uuid.UUID | None = None,
        sort_order: int = 0,
        parse_status: str | None = None,
    ) -> HubItem:
        row = HubItem(
            id=item_id or uuid.uuid4(),
            user_id=user_id,
            folder_id=folder_id,
            item_kind=item_kind,
            filename=filename,
            mime_type=mime_type,
            size_bytes=size_bytes,
            content_hash=content_hash,
            provider=provider,
            provider_file_id=provider_file_id,
            attachment_role=attachment_role,
            capture_id=capture_id,
            sort_order=sort_order,
            parse_status=parse_status or "pending",
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def move_to_folder(self, row: HubItem, folder_id: uuid.UUID) -> HubItem:
        row.folder_id = folder_id
        await self._session.flush()
        return row

    async def list_parts(self, capture_id: uuid.UUID) -> list[HubItem]:
        result = await self._session.execute(
            select(HubItem)
            .where(
                HubItem.capture_id == capture_id,
                HubItem.attachment_role == "audio_part",
            )
            .order_by(HubItem.sort_order.asc(), HubItem.created_at.asc())
        )
        return list(result.scalars())

    async def count_parts(self, capture_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count(HubItem.id)).where(
                HubItem.capture_id == capture_id,
                HubItem.attachment_role == "audio_part",
            )
        )
        return int(result.scalar_one() or 0)

    async def delete(self, row: HubItem) -> None:
        await self._session.delete(row)
        await self._session.flush()
