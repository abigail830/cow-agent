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
from app.db.repositories.messages import MessageRepository
from app.memory.maf_mapping import row_to_dict
from app.memory.memory_config import MemoryConfig
from app.memory.turn_window import take_last_turns

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 60 * 60 * 24
WORKING_SET_VERSION = 1
# Extensions that must survive redis/DB merge (redis may lag behind DB on cold start).
_PERSISTED_EXTENSION_KEYS = ("proposal_draft", "fulfillment_forms")


class SessionStore:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._messages = MessageRepository(db)

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
        """Merge a top-level key into the chat session payload (e.g. proposal_state)."""
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

    async def get_working_set_rows(
        self,
        chat_id: uuid.UUID,
        memory_config: MemoryConfig,
        *,
        exclude_from_sequence: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return working-set rows for model injection (prior turns only, full fidelity)."""
        payload = await self._load_payload(chat_id)
        working_set = _extract_working_set(payload)

        if _working_set_valid(working_set, memory_config):
            rows = list(working_set.get("rows") or [])
        else:
            rows = await self._rebuild_working_set(chat_id, memory_config, cold=True)
            payload = await self._load_payload(chat_id) or {}
            working_set = _extract_working_set(payload)
            rows = list((working_set or {}).get("rows") or rows)

        if exclude_from_sequence is not None:
            rows = [r for r in rows if int(r.get("sequence") or 0) < exclude_from_sequence]
        return rows

    async def append_completed_turn(
        self,
        chat_id: uuid.UUID,
        memory_config: MemoryConfig,
        *,
        turn_start_sequence: int,
    ) -> None:
        """Append a completed turn from DB into the Redis working set."""
        all_rows = await self._load_db_rows(chat_id)
        turn_rows = [r for r in all_rows if int(r.get("sequence") or 0) >= turn_start_sequence]
        if not turn_rows:
            return

        payload = await self._load_payload(chat_id) or {}
        working_set = _extract_working_set(payload)
        existing_rows: list[dict[str, Any]] = []

        if _working_set_valid(working_set, memory_config):
            existing_rows = list(working_set.get("rows") or [])
        else:
            existing_rows = await self._rebuild_working_set(chat_id, memory_config, cold=True)
            payload = await self._load_payload(chat_id) or {}
            working_set = _extract_working_set(payload)
            existing_rows = list((working_set or {}).get("rows") or existing_rows)

        existing_sequences = {int(r.get("sequence") or 0) for r in existing_rows}
        for row in turn_rows:
            seq = int(row.get("sequence") or 0)
            if seq in existing_sequences:
                continue
            existing_rows.append(row)
            existing_sequences.add(seq)

        existing_rows.sort(key=lambda r: int(r.get("sequence") or 0))
        trimmed = take_last_turns(existing_rows, memory_config.working_set_turns)
        last_sequence = max((int(r.get("sequence") or 0) for r in trimmed), default=0)

        payload["working_set"] = {
            "version": WORKING_SET_VERSION,
            "config_hash": memory_config.config_hash(),
            "last_sequence": last_sequence,
            "rows": trimmed,
        }
        await self._save_payload(chat_id, payload)

    async def _rebuild_working_set(
        self,
        chat_id: uuid.UUID,
        memory_config: MemoryConfig,
        *,
        cold: bool,
    ) -> list[dict[str, Any]]:
        all_rows = await self._load_db_rows(chat_id)
        max_turns = memory_config.cold_resume_max_turns if cold else memory_config.working_set_turns
        windowed = take_last_turns(all_rows, max_turns)
        last_sequence = max((int(r.get("sequence") or 0) for r in windowed), default=0)

        payload = await self._load_payload(chat_id) or {}
        if "session" not in payload:
            session = await self.get_session(chat_id)
            if session is not None:
                payload["session"] = session.to_dict()
            else:
                payload["session"] = AgentSession(session_id=str(chat_id)).to_dict()

        payload["working_set"] = {
            "version": WORKING_SET_VERSION,
            "config_hash": memory_config.config_hash(),
            "last_sequence": last_sequence,
            "rows": windowed,
        }
        await self._save_payload(chat_id, payload)
        return windowed

    async def _load_db_rows(self, chat_id: uuid.UUID) -> list[dict[str, Any]]:
        rows = await self._messages.list_by_chat(chat_id)
        return [row_to_dict(r) for r in rows]

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
        # Persisted extensions: DB is source of truth (Redis may lag or hold stale empties).
        for key in _PERSISTED_EXTENSION_KEYS:
            if key in db_payload:
                merged[key] = db_payload[key]
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


def _extract_working_set(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    working_set = payload.get("working_set")
    if isinstance(working_set, dict):
        return working_set
    return None


def _working_set_valid(working_set: dict[str, Any] | None, memory_config: MemoryConfig) -> bool:
    if not working_set:
        return False
    if working_set.get("version") != WORKING_SET_VERSION:
        return False
    if working_set.get("config_hash") != memory_config.config_hash():
        return False
    return isinstance(working_set.get("rows"), list)
