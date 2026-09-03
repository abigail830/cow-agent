"""Post-tool result truncation — MAF equivalent of Claude Agent SDK PostToolUse hook."""

from __future__ import annotations

import json
import logging
from typing import Any

from agent_framework import FunctionInvocationContext, FunctionMiddleware

from app.middleware.sql_tools import is_sql_run_query

logger = logging.getLogger(__name__)

DEFAULT_MAX_OBSERVATION_BYTES = 50_000


def _text_from_content_blocks(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            parts.append(str(block.get("text", "")))
        elif isinstance(block, dict):
            parts.append(json.dumps(block, ensure_ascii=False, default=str))
        else:
            parts.append(str(block))
    return "\n".join(parts)


def extract_response_text(tool_response: Any) -> str:
    """Normalize MCP / CLI tool_response shapes to a single text blob."""
    if tool_response is None:
        return ""
    if isinstance(tool_response, str):
        return tool_response
    if isinstance(tool_response, list):
        return _text_from_content_blocks(tool_response)
    if isinstance(tool_response, dict):
        if "content" in tool_response:
            return _text_from_content_blocks(tool_response.get("content"))
        return json.dumps(tool_response, ensure_ascii=False, default=str)
    return str(tool_response)


def wrap_truncated_output(original: Any, new_text: str) -> Any:
    """Preserve the tool_response shape where possible."""
    if isinstance(original, list):
        return [{"type": "text", "text": new_text}]
    if isinstance(original, dict) and "content" in original:
        return {
            **original,
            "content": [{"type": "text", "text": new_text}],
        }
    if isinstance(original, dict):
        try:
            return json.loads(new_text)
        except json.JSONDecodeError:
            return {"text": new_text, "truncated": True}
    return new_text


def truncate_observation_text(text: str, *, max_bytes: int) -> str:
    """Build truncated observation text for the model."""
    if not text or len(text.encode("utf-8")) <= max_bytes:
        return text

    try:
        data = json.loads(text)
        rows = data.get("rows", []) if isinstance(data, dict) else []
        summary = {
            "row_count": data.get("row_count", len(rows)) if isinstance(data, dict) else len(rows),
            "truncated": True,
            "sample_rows": rows[:5] if isinstance(rows, list) else [],
            "note": "Full result stored in platform DB; observation truncated for context",
        }
        return json.dumps(summary, ensure_ascii=False, default=str)
    except json.JSONDecodeError:
        encoded = text.encode("utf-8")
        if len(encoded) <= max_bytes:
            return text
        # Truncate on byte boundary without splitting UTF-8 code points.
        cut = encoded[:max_bytes].decode("utf-8", errors="ignore")
        return cut + "…[truncated]"


def truncate_tool_response(tool_response: Any, *, max_bytes: int) -> Any:
    """Return tool_response unchanged, or a truncated variant for LLM observation."""
    text = extract_response_text(tool_response)
    new_text = truncate_observation_text(text, max_bytes=max_bytes)
    if new_text == text:
        return tool_response
    return wrap_truncated_output(tool_response, new_text)


class ResultTruncatorMiddleware(FunctionMiddleware):
    """Truncate large SQL run_query results after execution (PostToolUse)."""

    def __init__(self, *, max_observation_bytes: int = DEFAULT_MAX_OBSERVATION_BYTES) -> None:
        self._max_bytes = max_observation_bytes

    async def process(self, context: FunctionInvocationContext, call_next) -> None:
        await call_next()

        if not is_sql_run_query(context.function.name):
            return

        try:
            context.result = truncate_tool_response(context.result, max_bytes=self._max_bytes)
        except Exception:
            logger.exception("ResultTruncatorMiddleware failed for %s", context.function.name)
