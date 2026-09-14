"""Build MAF user input and persist attachment metadata on messages."""

from __future__ import annotations

import uuid
from typing import Any

from app.platform.attachments.materialize import build_user_message_with_attachments
from app.platform.attachments.metadata import attachment_metadata


__all__ = [
    "build_user_run_input",
    "link_attachments_metadata",
    "user_message_attachment_metadata",
]


def build_user_run_input(
    content: str,
    attachments: list[Any],
    *,
    model_id: str | None = None,
    provider: str | None = None,
):
    if not attachments:
        return content.strip() or content
    chat_id = getattr(attachments[0], "chat_id", None)
    return build_user_message_with_attachments(
        content,
        attachments,
        chat_id=chat_id or uuid.UUID(int=0),
        model_id=model_id,
        provider=provider,
    )


def user_message_attachment_metadata(attachments: list[Any]) -> dict[str, Any]:
    if not attachments:
        return {}
    return {"attachments": [attachment_metadata(att) for att in attachments]}


def link_attachments_metadata(
    metadata: dict[str, Any],
    attachments: list[Any],
) -> dict[str, Any]:
    attachment_meta = user_message_attachment_metadata(attachments)
    if not attachment_meta:
        return metadata
    return {**metadata, **attachment_meta}
