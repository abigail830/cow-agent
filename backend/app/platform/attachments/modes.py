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
