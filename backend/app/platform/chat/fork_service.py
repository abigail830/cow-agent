"""Duplicate a chat session transcript for fork UX."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chat
from app.db.repositories.chat_messages import ChatMessageRepository
from app.db.repositories.chat_ui_annotations import ChatUiAnnotationRepository

_TITLE_MAX = 60


def build_fork_title(source_title: str | None) -> str:
    base = (source_title or "New Chat").strip() or "New Chat"
    if base.lower().startswith("fork-"):
        base = base[5:].lstrip() or "New Chat"
    title = f"fork-{base}"
    if len(title) <= _TITLE_MAX:
        return title
    return title[: _TITLE_MAX - 1].rstrip() + "…"


async def fork_chat(
    db: AsyncSession,
    *,
    source: Chat,
    user_id: uuid.UUID,
) -> tuple[Chat, Chat]:
    """Create a new chat with a copy of source transcript rows."""
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

    message_repo = ChatMessageRepository(db)
    annotation_repo = ChatUiAnnotationRepository(db)
    source_messages = await message_repo.list_by_chat(source.id)
    source_annotations = await annotation_repo.list_by_chat(source.id)

    message_id_map: dict[uuid.UUID, uuid.UUID] = {}
    turn_id_map: dict[uuid.UUID, uuid.UUID] = {}

    message_rows: list[dict[str, Any]] = []
    for message in source_messages:
        new_id = uuid.uuid4()
        message_id_map[message.id] = new_id
        new_turn_id = turn_id_map.setdefault(message.turn_id, uuid.uuid4())
        message_rows.append(
            {
                "id": new_id,
                "turn_id": new_turn_id,
                "body": message.body,
            }
        )

    if message_rows:
        await message_repo.insert_many(new_chat.id, message_rows, flush=True)

    annotation_rows: list[dict[str, Any]] = []
    for annotation in source_annotations:
        anchor = annotation.anchor_message_id
        annotation_rows.append(
            {
                "id": uuid.uuid4(),
                "turn_id": turn_id_map.get(annotation.turn_id, uuid.uuid4()),
                "kind": annotation.kind,
                "ref": annotation.ref,
                "display": dict(annotation.display or {}),
                "anchor_message_id": message_id_map.get(anchor) if anchor else None,
            }
        )

    if annotation_rows:
        await annotation_repo.insert_many(new_chat.id, annotation_rows, flush=True)

    await db.commit()
    await db.refresh(new_chat)
    return new_chat, source
