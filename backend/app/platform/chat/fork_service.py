"""Duplicate a chat session (messages only) for fork UX."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chat, Message
from app.db.repositories.messages import MessageRepository

_TITLE_MAX = 60


def build_fork_title(source_title: str | None) -> str:
    base = (source_title or "New Chat").strip() or "New Chat"
    # Avoid stacking fork- prefixes endlessly.
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
    """Create a new chat owned by user_id with a copy of source messages.

    Returns (new_chat, source_chat). Does not copy session_state, attachments, or artifacts.
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

    source_messages: list[Message] = await MessageRepository(db).list_by_chat(source.id)
    id_map: dict[uuid.UUID, uuid.UUID] = {}
    rows: list[dict[str, Any]] = []

    for msg in source_messages:
        new_id = uuid.uuid4()
        id_map[msg.id] = new_id
        parent_id = None
        if msg.parent_id is not None:
            parent_id = id_map.get(msg.parent_id)
        rows.append(
            {
                "message_id": new_id,
                "role": msg.role,
                "content": msg.content,
                "message_type": msg.message_type,
                "metadata": _copy_metadata(msg.message_metadata),
                "parent_id": parent_id,
                "sequence": int(msg.sequence),
            }
        )

    if rows:
        await MessageRepository(db).insert_many(new_chat.id, rows, flush=True)

    await db.commit()
    await db.refresh(new_chat)
    return new_chat, source
