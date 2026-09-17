"""Artifact download and preview URL helpers (shared across agents)."""

from __future__ import annotations

import uuid
from urllib.parse import quote


def artifact_download_url(chat_id: uuid.UUID, artifact_id: str, *, variant: str | None = None) -> str:
    base = f"/api/v1/chats/{chat_id}/artifacts/{artifact_id}"
    if variant:
        return f"{base}?format={variant}"
    return base


def artifact_preview_url(chat_id: uuid.UUID, artifact_id: str) -> str:
    # No trailing slash: Vercel frontend /api rewrites 404 on `/preview/`.
    return f"/api/v1/chats/{chat_id}/artifacts/{artifact_id}/preview"


def content_disposition_attachment(filename: str) -> str:
    """Build a latin-1-safe Content-Disposition for Starlette Response headers.

    Non-ASCII names (e.g. Chinese titles) must use RFC 5987 ``filename*``;
    a bare ``filename="…"`` with CJK raises UnicodeEncodeError in Starlette.
    """
    raw = (filename or "download").replace("\\", "/").split("/")[-1].replace('"', "'")
    ascii_name = raw.encode("ascii", "ignore").decode("ascii").strip() or "download"
    encoded = quote(raw, safe="")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"
