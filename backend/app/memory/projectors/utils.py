"""Shared preview helpers for memory projectors."""

from __future__ import annotations

import json
from typing import Any


def ensure_dict(value: Any) -> dict[str, Any]:
    """Coerce metadata arguments/result shapes into a dict for safe .get() access."""
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return {}
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            return {"raw": stripped}
    return {}


def stringify_function_call_arguments(value: Any) -> str:
    """OpenAI Responses API requires function_call.arguments to be a JSON string."""
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or "{}"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    coerced = ensure_dict(value)
    return json.dumps(coerced, ensure_ascii=False) if coerced else "{}"


def preview_text(text: str, max_chars: int, *, label: str = "") -> str:
    cleaned = " ".join((text or "").split())
    if not cleaned:
        return label or ""
    if len(cleaned) <= max_chars:
        return f"{label}{cleaned}" if label else cleaned
    snippet = cleaned[:max_chars].rstrip()
    suffix = "…" if len(cleaned) > max_chars else ""
    return f"{label}{snippet}{suffix}" if label else f"{snippet}{suffix}"


def preview_json(obj: Any, max_chars: int) -> str:
    try:
        text = json.dumps(obj, ensure_ascii=False, default=str)
    except TypeError:
        text = str(obj)
    return preview_text(text, max_chars)


def mark_slimmed(metadata: dict[str, Any], *, projector: str) -> dict[str, Any]:
    return {**metadata, "memory_slimmed": True, "memory_projector": projector}


def extract_row_count(content: str | None, metadata: dict[str, Any]) -> int | None:
    result = metadata.get("result")
    if isinstance(result, dict):
        row_count = result.get("row_count")
        if isinstance(row_count, int):
            return row_count
        rows = result.get("rows")
        if isinstance(rows, list):
            return len(rows)
    if not content:
        return None
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return None
    if isinstance(parsed, dict):
        row_count = parsed.get("row_count")
        if isinstance(row_count, int):
            return row_count
        rows = parsed.get("rows")
        if isinstance(rows, list):
            return len(rows)
    return None


def is_truncated(content: str | None, metadata: dict[str, Any]) -> bool:
    if metadata.get("truncated") is True:
        return True
    result = metadata.get("result")
    if isinstance(result, dict) and result.get("truncated") is True:
        return True
    if not content:
        return False
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return False
    return isinstance(parsed, dict) and parsed.get("truncated") is True
