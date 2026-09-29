"""Parsed document figure helpers (shared by internal worker API and chat downloads)."""

from __future__ import annotations

import re
import uuid
from typing import Any

from app.platform.docstore.blob import load_parsed_artifact_scoped, load_parsed_figure, load_parsed_figure_scoped
from app.platform.docstore.figure_meta import (
    load_parsed_meta_json,
    resolve_figure_storage_id,
    strip_figure_ref,
)
from app.platform.docstore.scope import DocumentScope

_FIGURE_ID_RE = re.compile(r"^f\d+$")
_FIGURE_EXTENSIONS = ("jpeg", "jpg", "png", "gif", "webp")
_EXT_MEDIA_TYPES = {
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


def normalize_figure_id(raw: str) -> str:
    figure_id = strip_figure_ref(raw)
    if not _FIGURE_ID_RE.match(figure_id):
        raise ValueError(f"invalid figure id: {raw!r}")
    return figure_id


def normalize_figure_ref(raw: str, meta: dict[str, Any] | None = None) -> str:
    """Accept figure:fN, fN.ext, or Document Mind hash filename stems."""
    return resolve_figure_storage_id(raw, meta)


def _load_scoped_meta(scope: DocumentScope) -> dict[str, Any] | None:
    try:
        raw = load_parsed_artifact_scoped(scope, "meta_json")
    except FileNotFoundError:
        return None
    return load_parsed_meta_json(raw)


def load_parsed_figure_resolved(
    chat_id: uuid.UUID,
    attachment_id: uuid.UUID,
    figure_id: str,
) -> tuple[bytes, str]:
    """Load figure bytes, probing known extensions. Returns (data, media_type)."""
    return load_parsed_figure_resolved_with_meta(chat_id, attachment_id, figure_id)


def _load_figure_bytes_resolved(
    loader,
    storage_id: str,
) -> tuple[bytes, str]:
    last_error: FileNotFoundError | None = None
    for extension in _FIGURE_EXTENSIONS:
        try:
            data = loader(storage_id, extension)
        except FileNotFoundError as exc:
            last_error = exc
            continue
        media_type = _EXT_MEDIA_TYPES.get(extension, "application/octet-stream")
        return data, media_type
    raise FileNotFoundError(f"{storage_id}") from last_error


def load_parsed_figure_scoped_resolved(
    scope: DocumentScope,
    figure_id: str,
    *,
    meta: dict[str, Any] | None = None,
) -> tuple[bytes, str]:
    """Load scoped figure bytes, probing known extensions."""
    if meta is None:
        meta = _load_scoped_meta(scope)
    storage_id = normalize_figure_ref(figure_id, meta)

    def scoped_loader(sid: str, extension: str) -> bytes:
        return load_parsed_figure_scoped(scope, sid, extension)

    return _load_figure_bytes_resolved(scoped_loader, storage_id)


def load_parsed_figure_resolved_with_meta(
    chat_id: uuid.UUID,
    attachment_id: uuid.UUID,
    figure_id: str,
    *,
    meta: dict[str, Any] | None = None,
) -> tuple[bytes, str]:
    if meta is None:
        scope = DocumentScope.chat(chat_id, attachment_id)
        meta = _load_scoped_meta(scope)
    storage_id = normalize_figure_ref(figure_id, meta)

    def chat_loader(sid: str, extension: str) -> bytes:
        return load_parsed_figure(chat_id, attachment_id, sid, extension)

    return _load_figure_bytes_resolved(chat_loader, storage_id)
