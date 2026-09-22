import json
import logging
import uuid
from typing import Any

from agent_framework import AgentSession
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chat
from app.db.redis_client import get_redis, is_redis_available

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 60 * 60 * 24
# Redis is source of truth for hot session identity. DB overlays non-core extension keys.
_CORE_PAYLOAD_KEYS = frozenset({"session", "type"})


class SessionStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    def _redis_key(self, chat_id: uuid.UUID) -> str:
        return f"session:{chat_id}"

    async def get_session(self, chat_id: uuid.UUID) -> AgentSession | None:
        payload = await self._load_payload(chat_id)
        if payload is None:
            return None
        session_data = _extract_session_dict(payload)
        if session_data is None:
            return None
        try:
            return AgentSession.from_dict(session_data)
        except Exception:
            logger.exception("Invalid session payload for chat %s", chat_id)
            return None

    async def save_session(self, chat_id: uuid.UUID, session: AgentSession) -> None:
        payload = await self._load_payload(chat_id) or {}
        payload["session"] = session.to_dict()
        await self._save_payload(chat_id, payload)

    async def get_payload(self, chat_id: uuid.UUID) -> dict[str, Any]:
        payload = await self._load_payload(chat_id)
        return payload if payload is not None else {}

    async def merge_extension(self, chat_id: uuid.UUID, key: str, value: Any) -> None:
        """Merge a top-level key into the chat session payload."""
        payload = await self._load_payload(chat_id) or {}
        payload[key] = value
        await self._save_payload(chat_id, payload)

    async def get_or_create(self, chat_id: uuid.UUID) -> AgentSession:
        existing = await self.get_session(chat_id)
        if existing is not None:
            return existing
        session = AgentSession(session_id=str(chat_id))
        await self.save_session(chat_id, session)
        return session

    async def finalize_run(
        self,
        chat_id: uuid.UUID,
        session: AgentSession,
        *,
        payload_extensions: dict[str, Any] | None = None,
    ) -> None:
        """Persist MAF session identity and agent extension keys after a run."""
        payload = await self._load_payload(chat_id) or {}
        if payload_extensions:
            payload.update(payload_extensions)
        payload["session"] = session.to_dict()
        await self._save_payload(chat_id, payload)

    async def _load_payload_from_db(self, chat_id: uuid.UUID) -> dict[str, Any] | None:
        result = await self._db.execute(select(Chat).where(Chat.id == chat_id))
        chat = result.scalar_one_or_none()
        if chat and chat.session_state and isinstance(chat.session_state, dict):
            return chat.session_state
        return None

    async def _load_payload(self, chat_id: uuid.UUID) -> dict[str, Any] | None:
        db_payload = await self._load_payload_from_db(chat_id)
        cached = await self._get_from_redis(chat_id)
        if cached is None:
            return db_payload
        if db_payload is None:
            return cached
        merged = dict(cached)
        for key, value in db_payload.items():
            if key not in _CORE_PAYLOAD_KEYS:
                merged[key] = value
        return merged

    async def _save_payload(self, chat_id: uuid.UUID, payload: dict[str, Any]) -> None:
        await self._set_redis(chat_id, payload)

        result = await self._db.execute(select(Chat).where(Chat.id == chat_id))
        chat = result.scalar_one_or_none()
        if chat is not None:
            chat.session_state = payload
            flag_modified(chat, "session_state")
            await self._db.flush()

    async def _get_from_redis(self, chat_id: uuid.UUID) -> dict | None:
        if not is_redis_available():
            return None
        try:
            raw = await get_redis().get(self._redis_key(chat_id))
            if raw:
                return json.loads(raw)
        except Exception:
            logger.debug("Redis session read failed for %s; falling back to DB", chat_id)
        return None

    async def delete_session(self, chat_id: uuid.UUID) -> None:
        """Drop the Redis hot cache for this chat. DB session_state is removed with the chat row."""
        try:
            await get_redis().delete(self._redis_key(chat_id))
        except Exception:
            logger.debug("Redis session delete failed for %s", chat_id)

    async def _set_redis(self, chat_id: uuid.UUID, payload: dict) -> None:
        if not is_redis_available():
            return
        try:
            await get_redis().set(
                self._redis_key(chat_id),
                json.dumps(payload),
                ex=SESSION_TTL_SECONDS,
            )
        except Exception:
            logger.debug("Redis session write failed for %s; DB snapshot still saved", chat_id)


def _extract_session_dict(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("type") == "session":
        return payload
    session = payload.get("session")
    if isinstance(session, dict):
        return session
    return None
