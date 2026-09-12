"""Build MAF user input and persist attachment metadata on messages."""

from __future__ import annotations

import uuid
from typing import Any

from agent_framework import Content, Message

from app.platform.attachments.attachment_adapters import attachment_metadata, attachments_to_maf_contents
from app.platform.attachments.unify_lite.message_builder import build_user_run_input_lite
from app.platform.attachments.unify_lite.types import ExtractedAttachment


__all__ = [
    "build_user_run_input",
    "build_user_run_input_lite",
    "link_attachments_metadata",
    "user_message_attachment_metadata",
]


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


def link_attachments_metadata(
    metadata: dict[str, Any],
    attachments: list[Any],
    *,
    attachment_mode: str | None = None,
) -> dict[str, Any]:
    attachment_meta = user_message_attachment_metadata(attachments)
    if not attachment_meta and not attachment_mode:
        return metadata
    merged = {**metadata}
    if attachment_meta:
        merged.update(attachment_meta)
    if attachment_mode:
        merged["attachment_mode"] = attachment_mode
    return merged
