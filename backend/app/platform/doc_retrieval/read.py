"""Slice content.md by line, page, or section."""

from __future__ import annotations

from typing import Any


READ_MAX_LINES = 2000
READ_MAX_BYTES = 128 * 1024


def _line_bounds(meta: dict[str, Any], *, page: int | None, section_id: str | None) -> tuple[int, int] | None:
    if section_id:
        for section in meta.get("sections") or []:
            if not isinstance(section, dict):
                continue
            if str(section.get("id") or "") == section_id:
                start = int(section.get("line_start") or 1)
                end = int(section.get("line_end") or start)
                return start, end
        return None
    if page is not None:
        for page_entry in meta.get("pages") or []:
            if not isinstance(page_entry, dict):
                continue
            if int(page_entry.get("page") or 0) == page:
                start = int(page_entry.get("line_start") or 1)
                end = int(page_entry.get("line_end") or start)
                return start, end
        return None
    return None


def read_content_slice(
    content: str,
    meta: dict[str, Any],
    *,
    line_start: int | None = None,
    line_end: int | None = None,
    page: int | None = None,
    section_id: str | None = None,
    max_lines: int = READ_MAX_LINES,
    max_bytes: int = READ_MAX_BYTES,
) -> dict[str, Any]:
    lines = content.splitlines()
    total_lines = len(lines)

    bounds = _line_bounds(meta, page=page, section_id=section_id)
    if bounds is not None:
        line_start, line_end = bounds
    if line_start is None:
        line_start = 1
    if line_end is None:
        line_end = total_lines if total_lines else 1

    start = max(1, int(line_start))
    end = max(start, int(line_end))
    if total_lines:
        end = min(end, total_lines)

    selected = lines[start - 1 : end]
    truncated_by_lines = False
    if len(selected) > max_lines:
        selected = selected[:max_lines]
        truncated_by_lines = True
        end = start + max_lines - 1

    text = "\n".join(selected)
    truncated_by_bytes = False
    encoded = text.encode("utf-8")
    if len(encoded) > max_bytes:
        text = encoded[:max_bytes].decode("utf-8", errors="ignore")
        truncated_by_bytes = True

    return {
        "line_start": start,
        "line_end": end,
        "line_count": len(selected),
        "total_lines": total_lines,
        "content": text,
        "truncated": truncated_by_lines or truncated_by_bytes,
        "page": page,
        "section_id": section_id,
    }
