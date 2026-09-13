"""Resolve the effective model for a chat (user preference + agent defaults)."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentModel, Chat
from app.platform.llm.model_catalog import ModelEntry, resolve_agent_model
from app.platform.llm.model_preference import get_model_preference


async def resolve_chat_model(db: AsyncSession, chat: Chat) -> ModelEntry:
    agent = await db.get(AgentModel, chat.agent_id)
    if agent is None:
        raise ValueError("Agent not found for chat")
    preference_id = await get_model_preference(db, chat.user_id, chat.agent_id)
    return resolve_agent_model(agent, preference_id)
