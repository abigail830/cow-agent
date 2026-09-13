"""Platform attachment pull tools (P5b)."""

from __future__ import annotations

import hashlib
import uuid
from typing import Annotated, Any

from agent_framework import tool

from app.platform.attachments.attachment_storage import load_inline_attachment, parse_inline_attachment_id
from app.platform.attachments.services.map import get_attachment_map_service
from app.platform.attachments.services.vision import get_attachment_vision_service
from app.platform.attachments.run_state import get_attachment_run_state
from app.platform.attachments.unify_lite.extractors.registry import extract_bytes
from app.platform.attachments.unify_lite.validation import is_unify_lite_image

ATTACHMENT_PULL_TOOL_NAMES = frozenset(
    {
        "read_attachment",
        "analyze_image",
        "map_attachment",
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
        "Use for documents (.txt, .docx, etc.) when you need verbatim text, specific numbers, "
        "or line-level detail beyond a summary. Optional query filters lines containing the term. "
        "Do NOT call this on multiple ids to summarize many documents — use map_attachment instead. "
        "For images, use analyze_image instead."
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
        "Analyze a chat image attachment and return a text summary (no raw image bytes). "
        "Use for a single image, diagram, chart, or screenshot when visual detail is needed. "
        "For summarizing many images, prefer map_attachment per id. "
        "For documents, use read_attachment instead."
    ),
)
async def analyze_image_tool(
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

    vision = await get_attachment_vision_service().describe(
        data=data,
        mime_type=record.mime_type,
        filename=record.filename,
        question=question,
    )
    if vision.get("status") != "ok":
        return dict(vision)

    payload: dict[str, Any] = {
        "status": "ok",
        "attachment_id": attachment_id,
        "filename": record.filename,
        "summary": vision.get("summary"),
        "confidence": vision.get("confidence", "ok"),
        "full_available": True,
        "media_type": vision.get("media_type") or record.mime_type,
        "size_bytes": vision.get("size_bytes") or len(data),
    }
    if question:
        payload["question"] = (question or "").strip() or None
    if vision.get("vision_resized"):
        payload["vision_resized"] = True
    return payload


@tool(
    name="map_attachment",
    description=(
        "Summarize one chat attachment by id. Use for multi-file tasks: summarize each relevant id "
        "separately (optionally with focus, e.g. '违约条款'). Returns a text summary only — not full content. "
        "For verbatim text, numbers, or line-level detail use read_attachment. For a single image detail "
        "use analyze_image. Do NOT call read_attachment on every id just to summarize many files."
    ),
)
async def map_attachment_tool(
    attachment_id: Annotated[str, "Chat attachment UUID from the catalog index."],
    focus: Annotated[
        str | None,
        "Optional scope, e.g. 'chapter 3', '违约条款', 'revenue table'.",
    ] = None,
) -> dict[str, Any]:
    result = await get_attachment_map_service().map_one(attachment_id, focus)
    return dict(result)


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
    "map_attachment": map_attachment_tool,
    "search_attachments": search_attachments_tool,
}
