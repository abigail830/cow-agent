"""Load / patch / confirm fulfillment forms stored in chat session."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentModel, Chat
from app.platform.session_store import SessionStore
from app.yl_worker2.fulfillment.client import FulfillmentApiError, FulfillmentClient
from app.yl_worker2.fulfillment.forms import build_create_body, merge_payload_patch
from app.yl_worker2.fulfillment.store import (
    FULFILLMENT_FORMS_KEY,
    load_fulfillment_forms_from_payload,
    wrap_forms_document,
)

YL_WORKER2_AGENT_SLUG = "yl-worker2"


async def _ensure_yl_worker2_chat(db: AsyncSession, chat_id: uuid.UUID) -> Chat:
    chat = await db.get(Chat, chat_id)
    if chat is None:
        raise ValueError(f"Chat not found: {chat_id}")
    agent = await db.get(AgentModel, chat.agent_id)
    if agent is None or agent.slug != YL_WORKER2_AGENT_SLUG:
        raise ValueError("Fulfillment forms are only available for yl-worker2 chats.")
    return chat


async def get_chat_fulfillment_forms(
    db: AsyncSession,
    chat_id: uuid.UUID,
) -> dict[str, Any]:
    await _ensure_yl_worker2_chat(db, chat_id)
    store = SessionStore(db)
    payload = await store.get_payload(chat_id)
    forms = load_fulfillment_forms_from_payload(payload)
    return {
        "chat_id": str(chat_id),
        "forms": forms,
        "count": len(forms),
    }


async def patch_chat_fulfillment_form(
    db: AsyncSession,
    chat_id: uuid.UUID,
    form_id: str,
    payload_patch: dict[str, Any],
) -> dict[str, Any]:
    await _ensure_yl_worker2_chat(db, chat_id)
    store = SessionStore(db)
    session_payload = await store.get_payload(chat_id)
    forms = load_fulfillment_forms_from_payload(session_payload)

    target = None
    for f in forms:
        if f.get("form_id") == form_id:
            target = f
            break
    if target is None:
        raise ValueError(f"Form not found: {form_id}")

    updated = merge_payload_patch(target, payload_patch)
    new_forms = [updated if f.get("form_id") == form_id else f for f in forms]
    await store.merge_extension(chat_id, FULFILLMENT_FORMS_KEY, wrap_forms_document(new_forms))
    await db.commit()
    return {"form": updated}


async def confirm_chat_fulfillment_form(
    db: AsyncSession,
    chat_id: uuid.UUID,
    form_id: str,
) -> dict[str, Any]:
    await _ensure_yl_worker2_chat(db, chat_id)
    store = SessionStore(db)
    session_payload = await store.get_payload(chat_id)
    forms = load_fulfillment_forms_from_payload(session_payload)

    target = None
    for f in forms:
        if f.get("form_id") == form_id:
            target = f
            break
    if target is None:
        raise ValueError(f"Form not found: {form_id}")
    if target.get("status") != "editing":
        raise ValueError(f"Form not confirmable: {target.get('status')}")

    body = build_create_body(target.get("payload") or {})
    client = FulfillmentClient()
    try:
        item = await client.confirm_branch_replenishment(body)
    except FulfillmentApiError as exc:
        raise ValueError(str(exc)) from exc

    activated = dict(target)
    activated["status"] = "activated"
    activated["fulfillment_item"] = item
    activated["confirmed_at"] = datetime.now(timezone.utc).isoformat()

    new_forms = [activated if f.get("form_id") == form_id else f for f in forms]
    await store.merge_extension(chat_id, FULFILLMENT_FORMS_KEY, wrap_forms_document(new_forms))
    await db.commit()
    return {
        "status": "activated",
        "form": activated,
        "fulfillment_item": item,
    }


async def reject_chat_fulfillment_form(
    db: AsyncSession,
    chat_id: uuid.UUID,
    form_id: str,
) -> dict[str, Any]:
    await _ensure_yl_worker2_chat(db, chat_id)
    store = SessionStore(db)
    session_payload = await store.get_payload(chat_id)
    forms = load_fulfillment_forms_from_payload(session_payload)

    found = False
    new_forms: list[dict[str, Any]] = []
    rejected: dict[str, Any] | None = None
    for f in forms:
        if f.get("form_id") == form_id:
            found = True
            rejected = dict(f)
            break
        new_forms.append(f)
    if not found or rejected is None:
        raise ValueError(f"Form not found: {form_id}")

    if rejected.get("status") == "rejected":
        raise ValueError("Form already cancelled")

    fulfillment_item = rejected.get("fulfillment_item")
    fulfillment_id = None
    if isinstance(fulfillment_item, dict):
        raw_id = fulfillment_item.get("id")
        if raw_id:
            fulfillment_id = str(raw_id)

    if fulfillment_id:
        client = FulfillmentClient()
        try:
            await client.invalidate([fulfillment_id])
        except FulfillmentApiError as exc:
            raise ValueError(str(exc)) from exc
        if isinstance(fulfillment_item, dict):
            fulfillment_item = dict(fulfillment_item)
            fulfillment_item["status"] = "作废"
            rejected["fulfillment_item"] = fulfillment_item

    rejected["status"] = "rejected"
    rejected["confirmed_at"] = datetime.now(timezone.utc).isoformat()
    new_forms.append(rejected)

    await store.merge_extension(chat_id, FULFILLMENT_FORMS_KEY, wrap_forms_document(new_forms))
    await db.commit()
    return {"status": "cancelled", "form": rejected}
