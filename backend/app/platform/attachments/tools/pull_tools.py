"""Platform attachment pull tools (P5b)."""

from __future__ import annotations

import base64
import hashlib
import uuid
from typing import Annotated, Any

from agent_framework import tool

from app.platform.attachments.attachment_storage import load_inline_attachment, parse_inline_attachment_id
from app.platform.attachments.run_state import get_attachment_run_state
from app.platform.attachments.unify_lite.extractors.registry import extract_bytes
from app.platform.attachments.unify_lite.validation import is_unify_lite_image

ATTACHMENT_PULL_TOOL_NAMES = frozenset(
    {
        "read_attachment",
        "analyze_image",
        "search_attachments",
    }
)

_READ_MAX_CHARS = 120_000


def _cache_key(attachment_id: str, query: str | None) -> str:
    normalized = (query or "").strip().lower()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{attachment_id}:{digest}"


def _resolve_record(attachment_id: str):
    state = get_attachment_run_state()
    if state is None:
        return None, {"status": "error", "message": "Attachment context is not initialized for this run."}
    record = state.attachments.get(attachment_id)
    if record is None:
        return None, {"status": "error", "message": "Attachment not found in this chat."}
    if str(record.chat_id) != str(state.chat_id):
        return None, {"status": "error", "message": "Attachment does not belong to this chat."}
    return record, None


@tool(
    name="read_attachment",
    description=(
        "Load full text content of a chat attachment by id. "
        "Use for documents (.txt, .docx, etc.) when the user references an attachment "
        "or you need details beyond the catalog gist. Optional query filters lines containing the term."
    ),
)
def read_attachment_tool(
    attachment_id: Annotated[str, "Chat attachment UUID from the catalog index."],
    query: Annotated[str | None, "Optional keyword to filter returned text."] = None,
) -> dict[str, Any]:
    cache_key = _cache_key(attachment_id, query)
    state = get_attachment_run_state()
    if state is not None:
        cached = state.read_cache.get(cache_key)
        if cached is not None:
            return {"status": "ok", "attachment_id": attachment_id, "content": cached, "cached": True}

    record, error = _resolve_record(attachment_id)
    if error:
        return error
    assert record is not None

    if is_unify_lite_image(filename=record.filename, mime_type=record.mime_type):
        return {
            "status": "error",
            "message": "This attachment is an image. Use analyze_image instead.",
        }

    try:
        blob_id = parse_inline_attachment_id(record.provider_file_id)
        data = load_inline_attachment(record.chat_id, blob_id)
    except (OSError, ValueError) as exc:
        return {"status": "error", "message": str(exc)}

    text, warnings, _ = extract_bytes(
        filename=record.filename,
        mime_type=record.mime_type,
        data=data,
    )
    if query:
        needle = query.strip().lower()
        if needle:
            lines = [line for line in text.splitlines() if needle in line.lower()]
            text = "\n".join(lines) if lines else f"(No lines matched query: {query})"

    if len(text) > _READ_MAX_CHARS:
        text = text[: _READ_MAX_CHARS] + "\n… [truncated]"

    if state is not None:
        state.record_read(cache_key, text, attachment_id=attachment_id)

    payload: dict[str, Any] = {
        "status": "ok",
        "attachment_id": attachment_id,
        "filename": record.filename,
        "content": text,
        "cached": False,
    }
    if warnings:
        payload["warnings"] = list(warnings)
    return payload


@tool(
    name="analyze_image",
    description=(
        "Load a chat image attachment for visual analysis. Returns base64-encoded image data "
        "for the model to inspect. Use when the user asks about an uploaded image or diagram."
    ),
)
def analyze_image_tool(
    attachment_id: Annotated[str, "Chat attachment UUID from the catalog index."],
    question: Annotated[str | None, "Optional focus question for the analysis."] = None,
) -> dict[str, Any]:
    record, error = _resolve_record(attachment_id)
    if error:
        return error
    assert record is not None

    if not is_unify_lite_image(filename=record.filename, mime_type=record.mime_type):
        return {
            "status": "error",
            "message": "This attachment is not an image. Use read_attachment instead.",
        }

    try:
        blob_id = parse_inline_attachment_id(record.provider_file_id)
        data = load_inline_attachment(record.chat_id, blob_id)
    except (OSError, ValueError) as exc:
        return {"status": "error", "message": str(exc)}

    state = get_attachment_run_state()
    if state is not None:
        state.page_in_ids.add(attachment_id)

    encoded = base64.b64encode(data).decode("ascii")
    return {
        "status": "ok",
        "attachment_id": attachment_id,
        "filename": record.filename,
        "media_type": record.mime_type,
        "size_bytes": len(data),
        "data_base64": encoded,
        "question": (question or "").strip() or None,
        "note": "Image bytes returned for vision analysis in this turn.",
    }


@tool(
    name="search_attachments",
    description=(
        "Search attachment catalog entries in the current chat by filename or gist text. "
        "Use when many attachments exist and you need to find the right id."
    ),
)
def search_attachments_tool(
    query: Annotated[str, "Search term matched against filename and gist."],
) -> dict[str, Any]:
    state = get_attachment_run_state()
    if state is None:
        return {"status": "error", "message": "Attachment context is not initialized for this run."}

    needle = query.strip().lower()
    if not needle:
        return {"status": "error", "message": "Query must not be empty."}

    matches: list[dict[str, Any]] = []
    for record in state.attachments.values():
        haystacks = [
            record.filename.lower(),
            (record.gist or "").lower(),
        ]
        if any(needle in value for value in haystacks if value):
            matches.append(
                {
                    "attachment_id": str(record.attachment_id),
                    "filename": record.filename,
                    "gist": record.gist or record.filename,
                }
            )
    return {"status": "ok", "query": query, "matches": matches, "count": len(matches)}


ATTACHMENT_PULL_BUILTIN_TOOLS: dict[str, Any] = {
    "read_attachment": read_attachment_tool,
    "analyze_image": analyze_image_tool,
    "search_attachments": search_attachments_tool,
}
