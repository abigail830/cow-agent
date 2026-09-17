import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserAgentKbPreference


class KbPreferenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_disabled_ids(self, user_id: uuid.UUID, agent_id: uuid.UUID) -> list[str]:
        result = await self._session.execute(
            select(UserAgentKbPreference.disabled_kb_ids).where(
                UserAgentKbPreference.user_id == user_id,
                UserAgentKbPreference.agent_id == agent_id,
            )
        )
        raw = result.scalar_one_or_none()
        if not isinstance(raw, list):
            return []
        return [str(item).strip() for item in raw if str(item).strip()]

    async def upsert_disabled_ids(
        self,
        user_id: uuid.UUID,
        agent_id: uuid.UUID,
        disabled_kb_ids: list[str],
    ) -> list[str]:
        cleaned = sorted({str(item).strip() for item in disabled_kb_ids if str(item).strip()})
        stmt = insert(UserAgentKbPreference).values(
            id=uuid.uuid4(),
            user_id=user_id,
            agent_id=agent_id,
            disabled_kb_ids=cleaned,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_user_agent_kb_preferences",
            set_={"disabled_kb_ids": cleaned, "updated_at": func.now()},
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return cleaned
