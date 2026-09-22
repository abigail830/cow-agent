"""MAF history provider factory — Redis SSOT with dev fallback."""

from __future__ import annotations

import logging
import os
import uuid

from agent_framework import InMemoryHistoryProvider, HistoryProvider
from agent_framework_redis import RedisHistoryProvider

from app.config import get_settings
from app.db.redis_client import check_redis_connection, get_redis

logger = logging.getLogger(__name__)

HISTORY_SOURCE_ID = "redis-history"
APPLICATION_ID = "agent-platform"

IS_VERCEL = os.getenv("VERCEL") == "1"


class RedisHistoryUnavailableError(RuntimeError):
    """Raised when agent history requires Redis but the connection is down."""


def _redis_history_required() -> bool:
    """Production (Vercel) requires Redis; local dev falls back unless explicitly forced."""
    settings = get_settings()
    if settings.redis_history_fallback == "in_memory":
        return False
    if IS_VERCEL:
        return True
    return settings.redis_history_required


def create_redis_history_provider(
    *,
    chat_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> RedisHistoryProvider:
    """Build a scoped Redis history provider using the platform shared Redis client."""
    settings = get_settings()
    provider = RedisHistoryProvider(
        source_id=HISTORY_SOURCE_ID,
        redis_url=settings.redis_url,
        key_prefix="chat",
        application_id=APPLICATION_ID,
        agent_id=str(agent_id),
        key_format="scoped",
        load_messages=True,
        store_inputs=True,
        store_outputs=True,
    )
    # Reuse the platform pool (same URL/timeouts); avoids a second client per agent build.
    provider._redis_client = get_redis()
    return provider


def _in_memory_history_provider() -> InMemoryHistoryProvider:
    return InMemoryHistoryProvider(
        source_id=HISTORY_SOURCE_ID,
        load_messages=True,
        store_inputs=True,
        store_outputs=True,
    )


async def create_history_provider(
    *,
    chat_id: uuid.UUID,
    agent_id: uuid.UUID,
) -> HistoryProvider:
    """Return RedisHistoryProvider when Redis is up; optional in-memory fallback for local dev."""
    if await check_redis_connection():
        return create_redis_history_provider(chat_id=chat_id, agent_id=agent_id)

    if not _redis_history_required():
        logger.warning(
            "Redis unavailable for chat %s — using InMemoryHistoryProvider (session.state only). "
            "Set REDIS_URL=redis://localhost:6379/0 or fix network to use Redis SSOT.",
            chat_id,
        )
        return _in_memory_history_provider()

    raise RedisHistoryUnavailableError(
        "Agent conversation history requires Redis, but the connection failed. "
        "Verify REDIS_URL is reachable, or for local dev set "
        "REDIS_HISTORY_FALLBACK=in_memory or run Redis locally "
        "(brew install redis && redis-server, then REDIS_URL=redis://localhost:6379/0)."
    )
