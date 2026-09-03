"""Build MAF user input and persist attachment metadata on messages."""

from __future__ import annotations

import uuid
from typing import Any

from agent_framework import Content, Message

from app.platform.attachment_adapters import attachment_metadata, attachments_to_maf_contents


def build_user_run_input(content: str, attachments: list[Any]) -> str | Message:
    text = content.strip()
    if not attachments:
        return text
    contents: list[Content] = []
    if text:
        contents.append(Content.from_text(text))
    contents.extend(attachments_to_maf_contents(attachments))
    if not contents:
        contents.append(Content.from_text(""))
    return Message(role="user", contents=contents)


def user_message_attachment_metadata(attachments: list[Any]) -> dict[str, Any]:
    if not attachments:
        return {}
    return {"attachments": [attachment_metadata(att) for att in attachments]}


def link_attachments_metadata(metadata: dict[str, Any], attachments: list[Any]) -> dict[str, Any]:
    attachment_meta = user_message_attachment_metadata(attachments)
    if not attachment_meta:
        return metadata
    return {**metadata, **attachment_meta}
