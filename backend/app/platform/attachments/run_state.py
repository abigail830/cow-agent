"""Per-run attachment tool context (chat scope, read cache, page-in tracking)."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AttachmentRecord:
    attachment_id: uuid.UUID
    chat_id: uuid.UUID
    filename: str
    mime_type: str
    provider: str
    provider_file_id: str
    size_bytes: int
    gist: str | None = None
    content_hash: str | None = None


@dataclass
class AttachmentRunState:
    chat_id: uuid.UUID
    attachments: dict[str, AttachmentRecord] = field(default_factory=dict)
    read_cache: dict[str, str] = field(default_factory=dict)
    map_cache: dict[str, dict[str, Any]] = field(default_factory=dict)
    page_in_ids: set[str] = field(default_factory=set)
    # Current turn facts (model-driven strategy context)
    turn_mentioned_ids: list[str] = field(default_factory=list)
    turn_visibility: dict[str, str] = field(default_factory=dict)
    turn_inline_costs: dict[str, int] = field(default_factory=dict)
    turn_inline_budget_limit: int = 0
    turn_inline_budget_allows_full: bool = True
    turn_inline_budget_total_est: int = 0
    # inline_attachment tool: scheduled → injected (per run, idempotent)
    pending_inline: dict[str, str] = field(default_factory=dict)
    injected_inline_ids: set[str] = field(default_factory=set)

    def record_read(self, cache_key: str, payload: str, *, attachment_id: str | None = None) -> None:
        self.read_cache[cache_key] = payload
        if attachment_id:
            self.page_in_ids.add(attachment_id)

    def cached_read(self, attachment_id: str) -> str | None:
        return self.read_cache.get(attachment_id)


_run_state: ContextVar[AttachmentRunState | None] = ContextVar("attachment_run_state", default=None)


def init_attachment_run_state(
    *,
    chat_id: uuid.UUID,
    attachments: list[AttachmentRecord] | None = None,
) -> AttachmentRunState:
    state = AttachmentRunState(chat_id=chat_id)
    if attachments:
        for item in attachments:
            state.attachments[str(item.attachment_id)] = item
    _run_state.set(state)
    return state


def get_attachment_run_state() -> AttachmentRunState | None:
    return _run_state.get()


def reset_attachment_run_state() -> None:
    _run_state.set(None)


def attachment_records_from_rows(rows: list[Any]) -> list[AttachmentRecord]:
    records: list[AttachmentRecord] = []
    for row in rows:
        records.append(
            AttachmentRecord(
                attachment_id=row.id,
                chat_id=row.chat_id,
                filename=row.filename,
                mime_type=row.mime_type,
                provider=row.provider,
                provider_file_id=row.provider_file_id,
                size_bytes=row.size_bytes,
                gist=getattr(row, "gist", None),
                content_hash=getattr(row, "content_hash", None),
            )
        )
    return records
