"""Parse SQL MCP tool responses into tabular rows for visualization."""

from __future__ import annotations

import json
from typing import Any

from app.middleware.result_truncator import extract_response_text


def parse_sql_tool_result(tool_response: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (rows, column_names). Empty when unparseable."""
    text = extract_response_text(tool_response)
    if not text:
        return [], []

    data: Any
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [], []

    if not isinstance(data, dict):
        return [], []

    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        sample = data.get("sample_rows")
        if isinstance(sample, list):
            rows = sample
        else:
            return [], []

    normalized: list[dict[str, Any]] = []
    for item in rows:
        if isinstance(item, dict):
            normalized.append(dict(item))

    if not normalized:
        return [], []

    columns: list[str] = []
    seen: set[str] = set()
    for row in normalized:
        for key in row:
            if key not in seen:
                seen.add(key)
                columns.append(key)
    return normalized, columns
