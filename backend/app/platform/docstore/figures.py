"""Parsed document figure helpers (shared by internal worker API and chat downloads)."""

from __future__ import annotations

import re
import uuid

from app.platform.docstore.blob import load_parsed_figure

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
    figure_id = raw.strip()
    if "." in figure_id:
        figure_id = figure_id.rsplit(".", 1)[0]
    if not _FIGURE_ID_RE.match(figure_id):
        raise ValueError(f"invalid figure id: {raw!r}")
    return figure_id


def load_parsed_figure_resolved(
    chat_id: uuid.UUID,
    attachment_id: uuid.UUID,
    figure_id: str,
) -> tuple[bytes, str]:
    """Load figure bytes, probing known extensions. Returns (data, media_type)."""
    normalized_id = normalize_figure_id(figure_id)
    last_error: FileNotFoundError | None = None
    for extension in _FIGURE_EXTENSIONS:
        try:
            data = load_parsed_figure(chat_id, attachment_id, normalized_id, extension)
        except FileNotFoundError as exc:
            last_error = exc
            continue
        media_type = _EXT_MEDIA_TYPES.get(extension, "application/octet-stream")
        return data, media_type
    raise FileNotFoundError(f"{normalized_id}") from last_error
