from __future__ import annotations

import logging
import uuid

from app.db.redis_client import get_redis, is_redis_available

logger = logging.getLogger(__name__)

_PREF_CACHE: dict[tuple[str, str], str] = {}


def _cache_key(user_id: uuid.UUID, agent_id: uuid.UUID) -> tuple[str, str]:
    return (str(user_id), str(agent_id))


def _redis_key(user_id: uuid.UUID, agent_id: uuid.UUID) -> str:
    return f"model_pref:{user_id}:{agent_id}"


def invalidate_model_preference(user_id: uuid.UUID, agent_id: uuid.UUID) -> None:
    _PREF_CACHE.pop(_cache_key(user_id, agent_id), None)


async def get_model_preference(user_id: uuid.UUID, agent_id: uuid.UUID) -> str | None:
    key = _cache_key(user_id, agent_id)
    cached = _PREF_CACHE.get(key)
    if cached:
        return cached
    if not is_redis_available():
        return None
    try:
        value = await get_redis().get(_redis_key(user_id, agent_id))
    except Exception:
        logger.debug("Redis model preference read failed for user=%s agent=%s", user_id, agent_id)
        return None
    if value:
        _PREF_CACHE[key] = value
        return value
    return None


async def set_model_preference(user_id: uuid.UUID, agent_id: uuid.UUID, model_id: str) -> None:
    key = _cache_key(user_id, agent_id)
    _PREF_CACHE[key] = model_id
    if not is_redis_available():
        return
    try:
        await get_redis().set(_redis_key(user_id, agent_id), model_id)
    except Exception:
        logger.debug("Redis model preference write failed for user=%s agent=%s", user_id, agent_id)
