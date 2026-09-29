"""Builtin tools for chat attachment doc retrieval."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from agent_framework import tool

from app.platform.doc_retrieval.context import require_doc_retrieval_context
from app.platform.doc_retrieval.find import find_attachments
from app.platform.doc_retrieval.figures import read_figure_payload_for_entry
from app.platform.doc_retrieval.grep import grep_content, grep_matches_to_dict
from app.platform.doc_retrieval.read import read_content_slice
from app.platform.doc_retrieval.sections import list_sections
from app.platform.doc_retrieval.store import (
    DocRetrievalError,
    assert_chat_library_access,
    cached_meta,
    is_document_kind,
    library_for_scope,
    load_content_md_for_entry,
    load_pageindex_json_for_entry,
)

DOC_RETRIEVAL_TOOL_NAMES = frozenset(
    {
        "attachment_find",
        "attachment_list_chat",
        "attachment_grep",
        "attachment_read",
        "attachment_list_sections",
        "attachment_read_figure",
    }
)


def _error_payload(code: str, message: str) -> dict[str, Any]:
    return {"status": "error", "code": code, "message": message}


def _parse_attachment_id(attachment_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(attachment_id).strip())
    except ValueError as exc:
        raise DocRetrievalError("invalid_id", f"invalid attachment_id: {attachment_id}") from exc


@tool(
    name="attachment_find",
    description=(
        "Find imported session documents by fuzzy filename, kind, or topic. "
        "scope=session searches all imports in this chat; scope=turn limits to this message."
    ),
)
def attachment_find_tool(
    query: Annotated[str, "Natural language or keywords describing the attachment."],
    limit: Annotated[int, "Max candidates (default 5)."] = 5,
    scope: Annotated[
        Literal["session", "turn"],
        "session = full import list; turn = this message only.",
    ] = "session",
) -> dict[str, Any]:
    try:
        ctx = require_doc_retrieval_context()
        subset = library_for_scope(ctx, scope)
        candidates = find_attachments(subset, query, limit=max(1, min(limit, 10)))
        return {"status": "ok", "query": query, "scope": scope, "candidates": candidates}
    except DocRetrievalError as exc:
        return _error_payload(exc.code, exc.message)
    except RuntimeError as exc:
        return _error_payload("no_context", str(exc))


@tool(
    name="attachment_list_chat",
    description="List parse-ready documents in the session import list (compact catalog).",
)
def attachment_list_chat_tool(
    scope: Annotated[
        Literal["session", "turn"],
        "session = full import list; turn = this message only.",
    ] = "session",
) -> dict[str, Any]:
    try:
        ctx = require_doc_retrieval_context()
        subset = library_for_scope(ctx, scope)
        items = [
            {
                "attachment_id": entry.attachment_id,
                "filename": entry.filename,
                "kind": entry.kind,
                "mime_type": entry.mime_type,
                "source": entry.source,
                "page_count": entry.page_count,
                "line_count": entry.line_count,
                "figure_count": entry.figure_count,
                "parse_status": entry.parse_status,
                "created_at": entry.created_at,
            }
            for entry in sorted(
                subset.values(),
                key=lambda row: row.created_at or "",
                reverse=True,
            )
        ]
        return {"status": "ok", "scope": scope, "count": len(items), "attachments": items}
    except RuntimeError as exc:
        return _error_payload("no_context", str(exc))


@tool(
    name="attachment_grep",
    description="Search parsed content.md for a pattern. Use when attachment_id is known.",
)
def attachment_grep_tool(
    attachment_id: Annotated[str, "Chat attachment UUID."],
    pattern: Annotated[str, "Regex or plain text pattern."],
    ignore_case: Annotated[bool, "Case-insensitive search."] = True,
    head_limit: Annotated[int, "Max matches (default 50)."] = 50,
) -> dict[str, Any]:
    try:
        ctx = require_doc_retrieval_context()
        entry = assert_chat_library_access(ctx, attachment_id)
        if not is_document_kind(entry.kind):
            return _error_payload("unsupported_kind", "grep applies to parsed documents, not user images")
        _parse_attachment_id(attachment_id)
        content = load_content_md_for_entry(entry)
        matches = grep_content(content, pattern, ignore_case=ignore_case, head_limit=max(1, min(head_limit, 50)))
        return {
            "status": "ok",
            "attachment_id": attachment_id,
            "filename": entry.filename,
            "match_count": len(matches),
            "matches": grep_matches_to_dict(matches),
        }
    except DocRetrievalError as exc:
        return _error_payload(exc.code, exc.message)


@tool(
    name="attachment_read",
    description=(
        "Read a slice of parsed content.md by line range, page number, or section id. "
        "Content may contain figure:fN placeholders — use attachment_read_figure for images."
    ),
)
def attachment_read_tool(
    attachment_id: Annotated[str, "Chat attachment UUID."],
    line_start: Annotated[int | None, "1-based start line."] = None,
    line_end: Annotated[int | None, "1-based end line (inclusive)."] = None,
    page: Annotated[int | None, "Page number from meta.pages."] = None,
    section_id: Annotated[str | None, "Section id from meta.sections (e.g. s1)."] = None,
) -> dict[str, Any]:
    try:
        ctx = require_doc_retrieval_context()
        entry = assert_chat_library_access(ctx, attachment_id)
        if not is_document_kind(entry.kind):
            return _error_payload("unsupported_kind", "read applies to parsed documents, not user images")
        att_uuid = _parse_attachment_id(attachment_id)
        content = load_content_md_for_entry(entry)
        meta = cached_meta(ctx, att_uuid)
        result = read_content_slice(
            content,
            meta,
            line_start=line_start,
            line_end=line_end,
            page=page,
            section_id=section_id,
        )
        return {
            "status": "ok",
            "attachment_id": attachment_id,
            "filename": entry.filename,
            **result,
        }
    except DocRetrievalError as exc:
        return _error_payload(exc.code, exc.message)


@tool(
    name="attachment_list_sections",
    description="List document structure: sections, pages, figures summary from meta.json.",
)
def attachment_list_sections_tool(
    attachment_id: Annotated[str, "Chat attachment UUID."],
) -> dict[str, Any]:
    try:
        ctx = require_doc_retrieval_context()
        entry = assert_chat_library_access(ctx, attachment_id)
        att_uuid = _parse_attachment_id(attachment_id)
        meta = cached_meta(ctx, att_uuid)
        pageindex = load_pageindex_json_for_entry(entry)
        outline = list_sections(meta, pageindex)
        return {
            "status": "ok",
            "attachment_id": attachment_id,
            "filename": entry.filename,
            **outline,
        }
    except DocRetrievalError as exc:
        return _error_payload(exc.code, exc.message)


@tool(
    name="attachment_read_figure",
    description=(
        "Load a mirrored document figure (figure:fN) as base64 vision payload. "
        "Use after attachment_read shows figure:fN placeholders."
    ),
)
def attachment_read_figure_tool(
    attachment_id: Annotated[str, "Chat attachment UUID."],
    figure_id: Annotated[str, "Figure id from content or meta.figures (e.g. f1)."],
) -> dict[str, Any]:
    try:
        ctx = require_doc_retrieval_context()
        entry = assert_chat_library_access(ctx, attachment_id)
        att_uuid = _parse_attachment_id(attachment_id)
        meta = cached_meta(ctx, att_uuid)
        payload = read_figure_payload_for_entry(
            entry=entry,
            figure_id=str(figure_id).strip(),
            meta=meta,
        )
        return {
            "status": "ok",
            "attachment_id": attachment_id,
            "filename": entry.filename,
            **payload,
        }
    except DocRetrievalError as exc:
        return _error_payload(exc.code, exc.message)


DOC_RETRIEVAL_BUILTIN_TOOLS: dict[str, Any] = {
    "attachment_find": attachment_find_tool,
    "attachment_list_chat": attachment_list_chat_tool,
    "attachment_grep": attachment_grep_tool,
    "attachment_read": attachment_read_tool,
    "attachment_list_sections": attachment_list_sections_tool,
    "attachment_read_figure": attachment_read_figure_tool,
}
