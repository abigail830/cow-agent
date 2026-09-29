from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HubFolder


class HubFolderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_user(self, user_id: uuid.UUID) -> list[HubFolder]:
        result = await self._session.execute(
            select(HubFolder)
            .where(HubFolder.user_id == user_id)
            .order_by(HubFolder.sort_order.asc(), HubFolder.name.asc())
        )
        return list(result.scalars())

    async def get_owned(self, user_id: uuid.UUID, folder_id: uuid.UUID) -> HubFolder | None:
        row = await self._session.get(HubFolder, folder_id)
        if row is None or row.user_id != user_id:
            return None
        return row

    async def create(
        self,
        *,
        user_id: uuid.UUID,
        name: str,
        parent_id: uuid.UUID | None = None,
    ) -> HubFolder:
        row = HubFolder(
            id=uuid.uuid4(),
            user_id=user_id,
            parent_id=parent_id,
            name=name.strip(),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def rename(self, folder: HubFolder, name: str) -> HubFolder:
        folder.name = name.strip()
        await self._session.flush()
        return folder

    async def delete(self, folder: HubFolder) -> None:
        await self._session.delete(folder)
        await self._session.flush()
