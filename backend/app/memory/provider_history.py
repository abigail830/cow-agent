"""Sanitize persisted chat rows when replaying history to a different model provider."""

from __future__ import annotations

import logging
from typing import Any

from app.platform.model_registry import ModelProvider

logger = logging.getLogger(__name__)

_TOOL_ROW_TYPES = frozenset({"tool_call", "tool_result", "mcp_call", "mcp_result"})


def is_anthropic_tool_call_id(call_id: str) -> bool:
    return call_id.startswith("toolu_")


def is_openai_tool_call_id(call_id: str) -> bool:
    return call_id.startswith("call_") and not call_id.startswith("toolu_")


def call_id_incompatible_with_provider(call_id: str, provider: str) -> bool:
    if not call_id:
        return False
    if provider == ModelProvider.AZURE_OPENAI.value:
        return is_anthropic_tool_call_id(call_id)
    if provider == ModelProvider.SILICONFLOW.value:
        return is_anthropic_tool_call_id(call_id)
    if provider == ModelProvider.AZURE_ANTHROPIC.value:
        return is_openai_tool_call_id(call_id)
    return False


def _row_call_id(row: dict[str, Any]) -> str:
    metadata = row.get("metadata") or {}
    return str(metadata.get("call_id") or "")


def sanitize_rows_for_provider(
    rows: list[dict[str, Any]],
    *,
    provider: str,
) -> list[dict[str, Any]]:
    """Drop tool rows whose call_id belongs to another provider's API format."""
    incompatible: set[str] = set()
    for row in rows:
        if row.get("message_type") not in _TOOL_ROW_TYPES:
            continue
        call_id = _row_call_id(row)
        if call_id and call_id_incompatible_with_provider(call_id, provider):
            incompatible.add(call_id)

    if not incompatible:
        return rows

    logger.info(
        "Dropped %d cross-provider tool call id(s) for provider=%s: %s",
        len(incompatible),
        provider,
        ", ".join(sorted(incompatible)[:5]),
    )

    sanitized: list[dict[str, Any]] = []
    for row in rows:
        if row.get("message_type") not in _TOOL_ROW_TYPES:
            sanitized.append(row)
            continue
        if _row_call_id(row) in incompatible:
            continue
        sanitized.append(row)
    return sanitized
