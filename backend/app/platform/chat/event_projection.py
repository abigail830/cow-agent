"""Project chat_events rows to API MessageOut dicts."""

from __future__ import annotations

import uuid
from typing import Any

from app.db.models import ChatEvent


def event_to_dict(event: ChatEvent) -> dict[str, Any]:
    payload = event.payload if isinstance(event.payload, dict) else {}
    parent_raw = payload.get("parent_id")
    return {
        "id": str(event.id),
        "chat_id": str(event.chat_id),
        "role": payload.get("role") or "",
        "message_type": payload.get("message_type") or "text",
        "content": payload.get("content"),
        "metadata": payload.get("metadata") or {},
        "parent_id": str(parent_raw) if parent_raw else None,
        "sequence": int(event.sequence),
        "created_at": event.created_at.isoformat() if event.created_at else None,
    }


def turn_row_dict_to_out(chat_id: uuid.UUID, row: dict[str, Any]) -> dict[str, Any]:
    """Convert a persisted turn row dict into API MessageOut shape."""
    event_id = row.get("id") or row.get("message_id")
    return {
        "id": str(event_id) if event_id else "",
        "chat_id": str(chat_id),
        "role": row["role"],
        "message_type": row["message_type"],
        "content": row.get("content"),
        "metadata": row.get("metadata") or {},
        "parent_id": row.get("parent_id"),
        "sequence": int(row["sequence"]),
        "created_at": row.get("created_at"),
    }


def build_turn_message_outs(
    chat_id: uuid.UUID,
    user_event: ChatEvent | None,
    turn_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    outs: list[dict[str, Any]] = []
    if user_event is not None:
        outs.append(event_to_dict(user_event))
    outs.extend(turn_row_dict_to_out(chat_id, row) for row in turn_rows)
    return outs
