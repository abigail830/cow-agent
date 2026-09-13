import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UserAgentModelPreference


class ModelPreferenceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: uuid.UUID, agent_id: uuid.UUID) -> str | None:
        result = await self._session.execute(
            select(UserAgentModelPreference.model_id).where(
                UserAgentModelPreference.user_id == user_id,
                UserAgentModelPreference.agent_id == agent_id,
            )
        )
        return result.scalar_one_or_none()

    async def upsert(self, user_id: uuid.UUID, agent_id: uuid.UUID, model_id: str) -> None:
        stmt = insert(UserAgentModelPreference).values(
            id=uuid.uuid4(),
            user_id=user_id,
            agent_id=agent_id,
            model_id=model_id,
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_user_agent_model_preferences",
            set_={"model_id": model_id, "updated_at": func.now()},
        )
        await self._session.execute(stmt)
        await self._session.flush()
