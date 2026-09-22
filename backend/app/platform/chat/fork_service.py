"""Duplicate a chat session (UI events only) for fork UX."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chat
from app.db.repositories.chat_events import ChatEventRepository

_TITLE_MAX = 60


def build_fork_title(source_title: str | None) -> str:
    base = (source_title or "New Chat").strip() or "New Chat"
    if base.lower().startswith("fork-"):
        base = base[5:].lstrip() or "New Chat"
    title = f"fork-{base}"
    if len(title) <= _TITLE_MAX:
        return title
    return title[: _TITLE_MAX - 1].rstrip() + "…"


def _copy_metadata(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    return {}


async def fork_chat(
    db: AsyncSession,
    *,
    source: Chat,
    user_id: uuid.UUID,
) -> tuple[Chat, Chat]:
    """Create a new chat with a copy of source UI events.

    Does not copy Redis MAF history, session_state, or attachments.
    """
    if source.user_id != user_id:
        raise PermissionError("Cannot fork another user's chat")

    source_title = source.title
    new_chat = Chat(
        user_id=user_id,
        agent_id=source.agent_id,
        title=build_fork_title(source_title),
        session_state={},
    )
    db.add(new_chat)
    await db.flush()

    source_events = await ChatEventRepository(db).list_by_chat(source.id)
    id_map: dict[uuid.UUID, uuid.UUID] = {}
    rows: list[dict[str, Any]] = []

    for event in source_events:
        new_id = uuid.uuid4()
        id_map[event.id] = new_id
        payload = event.payload if isinstance(event.payload, dict) else {}
        parent_raw = payload.get("parent_id")
        parent_id = None
        if parent_raw:
            try:
                parent_uuid = uuid.UUID(str(parent_raw))
                parent_id = id_map.get(parent_uuid)
            except ValueError:
                parent_id = None
        rows.append(
            {
                "message_id": new_id,
                "role": payload.get("role") or "user",
                "content": payload.get("content"),
                "message_type": payload.get("message_type") or "text",
                "metadata": _copy_metadata(payload.get("metadata")),
                "parent_id": parent_id,
                "sequence": int(event.sequence),
                "event_type": event.event_type,
            }
        )

    if rows:
        await ChatEventRepository(db).insert_many(new_chat.id, rows, flush=True)

    await db.commit()
    await db.refresh(new_chat)
    return new_chat, source
