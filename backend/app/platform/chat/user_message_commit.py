"""Shared helpers for early-commit user MAF messages."""

from __future__ import annotations

import uuid
from typing import Any

from agent_framework import Content, Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Chat
from app.db.repositories.attachments import AttachmentRepository
from app.db.repositories.chat_messages import ChatMessageRepository
from app.platform.attachments.materialize import build_user_message_with_attachments


def build_user_maf_message(
    chat_id: uuid.UUID,
    content: str,
    attachments: list[Any],
    *,
    model_id: str | None = None,
    model_provider: str | None = None,
    metadata: dict[str, Any] | None = None,
    already_full_inlined: set[str] | None = None,
) -> Message:
    run_input = build_user_message_with_attachments(
        content,
        attachments,
        chat_id=chat_id,
        model_id=model_id,
        provider=model_provider,
        already_full_inlined=already_full_inlined,
    )
    if isinstance(run_input, Message):
        message = run_input
    else:
        text = str(run_input or content).strip() or content
        message = Message(role="user", contents=[Content.from_text(text)])
    if metadata:
        props = dict(message.additional_properties or {})
        platform = dict(props.get("platform") or {})
        attachments = metadata.get("attachments")
        if attachments is not None:
            platform["attachments"] = attachments
        for key, value in metadata.items():
            if key != "attachments":
                platform[key] = value
        props["platform"] = platform
        message.additional_properties = props
    return message


async def persist_user_maf_message(
    db: AsyncSession,
    *,
    chat_id: uuid.UUID,
    turn_id: uuid.UUID,
    message: Message,
    run_id: uuid.UUID | None = None,
    attachment_ids: list[uuid.UUID] | None = None,
) -> Any:
    repo = ChatMessageRepository(db)
    row = await repo.insert(
        chat_id=chat_id,
        turn_id=turn_id,
        body=message.to_dict(),
        run_id=run_id,
    )
    if attachment_ids:
        await AttachmentRepository(db).link_to_message(attachment_ids, row.id)
    return row
