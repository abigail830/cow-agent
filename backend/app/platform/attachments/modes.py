"""Attachment processing mode — native (provider Files/Vision) vs unify-lite (platform extraction)."""

from __future__ import annotations

from enum import Enum


class AttachmentProcessingMode(str, Enum):
    NATIVE = "native"
    UNIFY_LITE = "unify_lite"


DEFAULT_ATTACHMENT_MODE = AttachmentProcessingMode.UNIFY_LITE


def parse_attachment_mode(value: str | None) -> AttachmentProcessingMode:
    if value is None or value == "":
        return DEFAULT_ATTACHMENT_MODE
    try:
        return AttachmentProcessingMode(value)
    except ValueError as exc:
        raise ValueError(
            f"Unknown attachment mode: {value!r}. Expected 'native' or 'unify_lite'."
        ) from exc


def attachment_pull_applies(metadata: dict | None = None, *, attachment_mode: str | None = None) -> bool:
    """Pull / THIN / catalog tools exist only for unify-lite turns."""
    raw_mode = attachment_mode
    if raw_mode is None and isinstance(metadata, dict):
        raw_mode = metadata.get("attachment_mode")
    if raw_mode:
        return parse_attachment_mode(str(raw_mode)) == AttachmentProcessingMode.UNIFY_LITE
    items = []
    if isinstance(metadata, dict):
        raw_items = metadata.get("attachments")
        if isinstance(raw_items, list):
            items = [item for item in raw_items if isinstance(item, dict)]
    if not items:
        return False
    return any(
        item.get("processing_mode") == AttachmentProcessingMode.UNIFY_LITE.value
        or item.get("provider") == AttachmentProcessingMode.UNIFY_LITE.value
        for item in items
    )
