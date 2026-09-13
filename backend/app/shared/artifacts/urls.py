"""Artifact download and preview URL helpers (shared across agents)."""

from __future__ import annotations

import uuid


def artifact_download_url(chat_id: uuid.UUID, artifact_id: str, *, variant: str | None = None) -> str:
    base = f"/api/v1/chats/{chat_id}/artifacts/{artifact_id}"
    if variant:
        return f"{base}?format={variant}"
    return base


def artifact_preview_url(chat_id: uuid.UUID, artifact_id: str) -> str:
    # No trailing slash: Vercel frontend /api rewrites 404 on `/preview/`.
    return f"/api/v1/chats/{chat_id}/artifacts/{artifact_id}/preview"
