"""Load persisted proposal draft and build live preview responses."""

from __future__ import annotations

import json
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentModel, Chat
from app.db.repositories.messages import MessageRepository
from app.platform.session_store import SessionStore
from app.proposal.draft import build_draft_preview
from app.proposal.preview import proposal_state_fingerprint
from app.proposal.store import load_proposal_draft_from_payload

PROPOSAL_AGENT_SLUG = "proposal-composer"
_DRAFT_RESULT_TOOLS = {
    "initialize_proposal_draft",
    "patch_proposal_draft",
    "add_package_to_proposal_draft",
    "add_services_to_proposal_draft",
    "remove_fee_rows_from_proposal_draft",
    "enable_proposal_draft_section",
}


def _coerce_tool_result(value) -> dict | None:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


async def _recover_proposal_draft_from_messages(
    db: AsyncSession,
    chat_id: uuid.UUID,
) -> dict | None:
    messages = await MessageRepository(db).list_by_chat(chat_id)
    for message in reversed(messages):
        if message.message_type != "tool_result":
            continue
        meta = message.message_metadata or {}
        if meta.get("tool_name") not in _DRAFT_RESULT_TOOLS:
            continue
        result = _coerce_tool_result(meta.get("result"))
        if not isinstance(result, dict) or result.get("status") != "ok":
            continue
        draft = result.get("draft")
        if isinstance(draft, dict) and draft:
            return draft
    return None


async def load_chat_proposal_draft(
    db: AsyncSession,
    chat_id: uuid.UUID,
) -> dict | None:
    chat = await db.get(Chat, chat_id)
    if chat is None:
        raise ValueError(f"Chat not found: {chat_id}")

    agent = await db.get(AgentModel, chat.agent_id)
    if agent is None or agent.slug != PROPOSAL_AGENT_SLUG:
        raise ValueError("Proposal draft is only available for Proposal Composer chats.")

    store = SessionStore(db)
    payload = await store.get_payload(chat_id)
    draft = load_proposal_draft_from_payload(payload)
    if draft is None:
        db_payload = await store._load_payload_from_db(chat_id)
        draft = load_proposal_draft_from_payload(db_payload)
    if draft is None:
        draft = await _recover_proposal_draft_from_messages(db, chat_id)
        if draft is not None:
            await store.merge_extension(chat_id, "proposal_draft", draft)
            await db.commit()
    return draft


async def get_chat_proposal_preview(
    db: AsyncSession,
    chat_id: uuid.UUID,
    *,
    draft: bool = True,
) -> dict:
    draft_state = await load_chat_proposal_draft(db, chat_id)
    if draft_state is None:
        preview = build_draft_preview({})
        preview["message"] = "Initialize a proposal draft to start the preview."
        preview["chat_id"] = str(chat_id)
        return preview
    preview = build_draft_preview(draft_state)
    preview["chat_id"] = str(chat_id)
    return preview


async def get_chat_proposal_draft(
    db: AsyncSession,
    chat_id: uuid.UUID,
) -> dict:
    draft_state = await load_chat_proposal_draft(db, chat_id)
    return {
        "chat_id": str(chat_id),
        "draft": draft_state or {},
        "state_fingerprint": proposal_state_fingerprint(draft_state or {}),
    }
