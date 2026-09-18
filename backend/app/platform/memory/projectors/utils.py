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


def truncate_long_strings(arguments: dict[str, Any], max_chars: int) -> dict[str, Any]:
    """Keep every argument key; truncate only string values that exceed max_chars.

    Used as a fallback when a tool family has no more specific slim rule.
    Does not invent synthetic keys and does not squeeze the whole JSON blob.
    """
    args = ensure_dict(arguments)
    if not args or max_chars <= 0:
        return dict(args)
    out: dict[str, Any] = {}
    for key, value in args.items():
        if isinstance(value, str):
            cleaned = " ".join(value.split())
            out[key] = preview_text(cleaned, max_chars) if len(cleaned) > max_chars else value
        else:
            out[key] = value
    return out


def truncate_named_string_fields(
    arguments: dict[str, Any],
    field_names: tuple[str, ...],
    max_chars: int,
) -> dict[str, Any]:
    """Keep the full argument dict; truncate only the first matching named string field.

    Domain projectors use this for focused call-side slimming (e.g. SQL text, query).
    """
    args = ensure_dict(arguments)
    if not args:
        return {}
    out = dict(args)
    if max_chars <= 0:
        return out
    for key in field_names:
        value = out.get(key)
        if isinstance(value, str) and value.strip():
            cleaned = " ".join(value.split())
            if len(cleaned) > max_chars:
                out[key] = preview_text(cleaned, max_chars)
            break
    return out


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
