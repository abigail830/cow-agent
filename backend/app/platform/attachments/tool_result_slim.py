"""Slim attachment pull tool payloads for persist and history replay."""

from __future__ import annotations

import json
from typing import Any, TypedDict

from app.config import get_settings
from app.platform.attachments.tools.pull_tools import ATTACHMENT_PULL_TOOL_NAMES
from app.platform.memory.projectors.utils import preview_text


class AttachmentArtifactSummary(TypedDict, total=False):
    """Durable attachment tool payload stored in history (no raw blobs)."""

    status: str
    attachment_id: str
    filename: str
    summary: str
    confidence: str
    content_hash: str
    full_available: bool
    persisted_summary: bool
    message: str
    cached: bool
    warnings: list[str]
    count: int
    matches: list[dict[str, Any]]


def is_attachment_pull_tool(tool_name: str) -> bool:
    return tool_name in ATTACHMENT_PULL_TOOL_NAMES


def extract_tool_payload(content: str | None, metadata: dict[str, Any]) -> dict[str, Any]:
    result = metadata.get("result")
    if isinstance(result, dict):
        return dict(result)
    if isinstance(result, str):
        stripped = result.strip()
        if stripped:
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {"status": "ok", "content": stripped}
    if content:
        stripped = content.strip()
        if stripped:
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                return {"status": "ok", "content": content}
    return {}


def build_persisted_attachment_payload(
    tool_name: str,
    payload: dict[str, Any],
    *,
    max_chars: int,
) -> dict[str, Any]:
    status = str(payload.get("status") or "ok")
    slimmed: dict[str, Any] = {
        "status": status,
        "full_available": status == "ok",
        "persisted_summary": True,
    }

    attachment_id = payload.get("attachment_id")
    if attachment_id is not None:
        slimmed["attachment_id"] = str(attachment_id)
    filename = payload.get("filename")
    if isinstance(filename, str) and filename:
        slimmed["filename"] = filename

    if status == "error":
        message = payload.get("message")
        if isinstance(message, str) and message:
            slimmed["message"] = preview_text(message, max_chars)
        return slimmed

    if tool_name == "map_attachment":
        summary = payload.get("summary")
        if isinstance(summary, str) and summary.strip():
            slimmed["summary"] = preview_text(summary, max_chars)
        confidence = payload.get("confidence")
        if isinstance(confidence, str) and confidence:
            slimmed["confidence"] = confidence
        if payload.get("cached") is True:
            slimmed["cached"] = True
        return slimmed

    if tool_name == "search_attachments":
        count = payload.get("count")
        slimmed["count"] = int(count) if isinstance(count, int) else 0
        query = payload.get("query")
        if isinstance(query, str) and query:
            slimmed["summary"] = preview_text(
                f"Search attachments: query={query!r}, count={slimmed['count']}.",
                max_chars,
            )
        else:
            slimmed["summary"] = preview_text(f"Search attachments: count={slimmed['count']}.", max_chars)
        matches = payload.get("matches")
        if isinstance(matches, list):
            slimmed["matches"] = [
                {
                    "attachment_id": str(item.get("attachment_id") or ""),
                    "filename": str(item.get("filename") or ""),
                    "gist": preview_text(str(item.get("gist") or ""), 120),
                }
                for item in matches[:8]
                if isinstance(item, dict)
            ]
        return slimmed

    if "data_base64" in payload:
        question = payload.get("question")
        summary = payload.get("summary") or payload.get("note") or "Image bytes are not stored in chat history."
        if isinstance(question, str) and question.strip():
            summary = f"{summary} Focus: {question.strip()}"
        slimmed["summary"] = preview_text(str(summary), max_chars)
        return slimmed

    text = payload.get("summary")
    if not isinstance(text, str) or not text.strip():
        text = payload.get("content")
    if not isinstance(text, str):
        text = ""
    slimmed["summary"] = preview_text(text, max_chars)

    confidence = payload.get("confidence")
    if isinstance(confidence, str) and confidence:
        slimmed["confidence"] = confidence
    content_hash = payload.get("content_hash")
    if isinstance(content_hash, str) and content_hash:
        slimmed["content_hash"] = content_hash
    if payload.get("cached") is True:
        slimmed["cached"] = True
    warnings = payload.get("warnings")
    if isinstance(warnings, list) and warnings:
        slimmed["warnings"] = [str(item) for item in warnings[:5]]

    return slimmed


def slim_attachment_tool_payload(
    tool_name: str,
    *,
    content: str | None,
    metadata: dict[str, Any],
    max_chars: int | None = None,
) -> tuple[str | None, dict[str, Any]]:
    """Return persisted-safe content + metadata for an attachment pull tool result."""
    limit = max_chars if max_chars is not None else get_settings().attachment_tool_result_max_chars
    payload = extract_tool_payload(content, metadata)
    slimmed = build_persisted_attachment_payload(tool_name, payload, max_chars=limit)
    serialized = json.dumps(slimmed, ensure_ascii=False)
    new_metadata = {
        **metadata,
        "result": slimmed,
        "attachment_persist_slimmed": True,
    }
    return serialized, new_metadata


def slim_attachment_tool_row(
    row: dict[str, Any],
    *,
    max_chars: int | None = None,
) -> dict[str, Any]:
    """Apply attachment persist slimming to a platform message row."""
    message_type = row.get("message_type") or ""
    if message_type not in ("tool_result", "mcp_result"):
        return row
    metadata = dict(row.get("metadata") or {})
    tool_name = str(metadata.get("tool_name") or "")
    if not is_attachment_pull_tool(tool_name):
        return row
    content, metadata = slim_attachment_tool_payload(
        tool_name,
        content=row.get("content"),
        metadata=metadata,
        max_chars=max_chars,
    )
    return {**row, "content": content, "metadata": metadata}
