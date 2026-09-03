import logging

import redis.asyncio as redis

from app.config import get_settings

logger = logging.getLogger(__name__)

_redis: redis.Redis | None = None
_redis_available: bool | None = None


def get_redis() -> redis.Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = redis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
        )
    return _redis


def is_redis_available() -> bool:
    return _redis_available is True


async def check_redis_connection() -> bool:
    global _redis_available
    try:
        ok = bool(await get_redis().ping())
    except Exception:
        ok = False
    _redis_available = ok
    return ok
