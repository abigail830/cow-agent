"""Per-user per-agent chat model preference — Postgres is the source of truth."""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.model_preferences import ModelPreferenceRepository


async def get_model_preference(
    db: AsyncSession,
    user_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> str | None:
    return await ModelPreferenceRepository(db).get(user_id, agent_id)


async def set_model_preference(
    db: AsyncSession,
    user_id: uuid.UUID,
    agent_id: uuid.UUID,
    model_id: str,
) -> None:
    await ModelPreferenceRepository(db).upsert(user_id, agent_id, model_id)
