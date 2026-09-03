"""Persist proposal draft inside chat session payload."""

from __future__ import annotations

import uuid
from typing import Any

from app.proposal.context import export_proposal_draft, get_run_proposal_state


PROPOSAL_DRAFT_KEY = "proposal_draft"


def load_proposal_draft_from_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    stored = payload.get(PROPOSAL_DRAFT_KEY)
    if not isinstance(stored, dict) or not stored:
        return None
    meta = stored.get("meta") or {}
    sections = ((stored.get("document") or {}).get("sections") or [])
    if not (meta.get("template_id") or sections):
        return None
    return stored


def merge_proposal_draft_into_payload(payload: dict[str, Any]) -> dict[str, Any]:
    ctx = get_run_proposal_state()
    if ctx is None or not ctx.draft_dirty:
        return payload
    merged = dict(payload)
    if ctx.draft_dirty and ctx.draft is not None:
        merged[PROPOSAL_DRAFT_KEY] = export_proposal_draft() or ctx.draft
    return merged


async def persist_proposal_draft_if_dirty(session_store, chat_id: uuid.UUID) -> None:
    """Persist dirty proposal draft into chat session payload."""
    ctx = get_run_proposal_state()
    if ctx is None or not ctx.draft_dirty:
        return
    if ctx.draft_dirty and ctx.draft is not None:
        await session_store.merge_extension(chat_id, PROPOSAL_DRAFT_KEY, ctx.draft)
        ctx.draft_dirty = False
