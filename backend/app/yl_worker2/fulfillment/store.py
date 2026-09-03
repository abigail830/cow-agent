"""Persist fulfillment_forms in chat session payload."""

from __future__ import annotations

import uuid
from typing import Any

from app.yl_worker2.fulfillment.context import get_run_fulfillment_forms_state

FULFILLMENT_FORMS_KEY = "fulfillment_forms"


def load_fulfillment_forms_from_payload(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    stored = payload.get(FULFILLMENT_FORMS_KEY)
    if not isinstance(stored, dict):
        return []
    forms = stored.get("forms")
    if not isinstance(forms, list):
        return []
    return [f for f in forms if isinstance(f, dict)]


def wrap_forms_document(forms: list[dict[str, Any]]) -> dict[str, Any]:
    return {"version": 1, "forms": forms}


async def persist_fulfillment_forms_if_dirty(session_store, chat_id: uuid.UUID) -> None:
    ctx = get_run_fulfillment_forms_state()
    if ctx is None or not ctx.dirty:
        return
    await session_store.merge_extension(
        chat_id,
        FULFILLMENT_FORMS_KEY,
        wrap_forms_document(ctx.forms),
    )
    ctx.dirty = False


async def save_fulfillment_forms(
    session_store,
    chat_id: uuid.UUID,
    forms: list[dict[str, Any]],
) -> None:
    await session_store.merge_extension(
        chat_id,
        FULFILLMENT_FORMS_KEY,
        wrap_forms_document(forms),
    )
    ctx = get_run_fulfillment_forms_state()
    if ctx is not None:
        ctx.forms = list(forms)
        ctx.dirty = False
