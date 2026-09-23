"""Per-run doc retrieval context (chat library + turn manifest ids)."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ChatAttachmentIndexEntry:
    attachment_id: str
    filename: str
    mime_type: str
    kind: str
    parse_status: str
    line_count: int | None = None
    page_count: int | None = None
    figure_count: int = 0
    gist: str | None = None
    created_at: str | None = None
    section_titles: tuple[str, ...] = ()


@dataclass
class DocRetrievalContext:
    chat_id: uuid.UUID
    turn_attachment_ids: frozenset[str] = frozenset()
    library: dict[str, ChatAttachmentIndexEntry] = field(default_factory=dict)
    meta_cache: dict[str, dict[str, Any]] = field(default_factory=dict)


_doc_retrieval_ctx: ContextVar[DocRetrievalContext | None] = ContextVar(
    "doc_retrieval_ctx",
    default=None,
)


def init_doc_retrieval_context(
    *,
    chat_id: uuid.UUID,
    library: dict[str, ChatAttachmentIndexEntry],
    turn_attachment_ids: frozenset[str] | None = None,
) -> DocRetrievalContext:
    ctx = DocRetrievalContext(
        chat_id=chat_id,
        turn_attachment_ids=turn_attachment_ids or frozenset(),
        library=library,
    )
    _doc_retrieval_ctx.set(ctx)
    return ctx


def get_doc_retrieval_context() -> DocRetrievalContext | None:
    return _doc_retrieval_ctx.get()


def require_doc_retrieval_context() -> DocRetrievalContext:
    ctx = get_doc_retrieval_context()
    if ctx is None:
        raise RuntimeError("doc retrieval context not initialized for this run")
    return ctx


def reset_doc_retrieval_context() -> None:
    _doc_retrieval_ctx.set(None)
