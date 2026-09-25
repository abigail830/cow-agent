"""Load agent profile ASR hotword/context text for capture jobs."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentModel, Chat
from app.platform.agent.profile_loader import AGENTS_ROOT, load_agent_profile


def _normalize_asr_context(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        text = raw.strip()
        return text or None
    if isinstance(raw, list):
        parts = [str(item).strip() for item in raw if str(item).strip()]
        return "\n".join(parts) if parts else None
    if isinstance(raw, dict):
        text = raw.get("text") or raw.get("context") or raw.get("hotwords")
        return _normalize_asr_context(text)
    text = str(raw).strip()
    return text or None


def asr_context_from_profile_extra(extra_config: dict[str, Any]) -> str | None:
    return _normalize_asr_context(extra_config.get("asr_context"))


async def load_asr_context_for_chat(session: AsyncSession, chat_id: uuid.UUID) -> str | None:
    chat = await session.get(Chat, chat_id)
    if chat is None:
        return None
    agent = await session.get(AgentModel, chat.agent_id)
    if agent is None or not agent.slug:
        return None
    agent_dir = AGENTS_ROOT / agent.slug
    if not agent_dir.is_dir():
        return None
    try:
        profile = load_agent_profile(agent_dir)
    except ValueError:
        return None
    return asr_context_from_profile_extra(profile.extra_config)
