from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserIntegration


class UserIntegrationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID, provider: str) -> UserIntegration | None:
        result = await self._session.execute(
            select(UserIntegration).where(
                UserIntegration.user_id == user_id,
                UserIntegration.provider == provider,
            )
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: uuid.UUID) -> list[UserIntegration]:
        result = await self._session.execute(
            select(UserIntegration)
            .where(UserIntegration.user_id == user_id)
            .order_by(UserIntegration.provider.asc())
        )
        return list(result.scalars().all())

    async def upsert_connected(
        self,
        *,
        user_id: uuid.UUID,
        provider: str,
        secrets_encrypted: str,
        account_label: str | None = None,
        integration_metadata: dict | None = None,
    ) -> UserIntegration:
        row = await self.get(user_id, provider)
        now = datetime.now(timezone.utc)
        if row is None:
            row = UserIntegration(
                user_id=user_id,
                provider=provider,
                status="connected",
                account_label=account_label,
                secrets_encrypted=secrets_encrypted,
                integration_metadata=integration_metadata or {},
                connection_version=1,
            )
            self._session.add(row)
        else:
            row.status = "connected"
            row.account_label = account_label
            row.secrets_encrypted = secrets_encrypted
            row.integration_metadata = integration_metadata or {}
            row.connection_version = int(row.connection_version or 0) + 1
            row.updated_at = now
        await self._session.flush()
        return row

    async def disconnect(self, user_id: uuid.UUID, provider: str) -> UserIntegration | None:
        row = await self.get(user_id, provider)
        if row is None:
            return None
        row.status = "disconnected"
        row.secrets_encrypted = ""
        row.account_label = None
        row.integration_metadata = {}
        row.connection_version = int(row.connection_version or 0) + 1
        row.updated_at = datetime.now(timezone.utc)
        await self._session.flush()
        return row
