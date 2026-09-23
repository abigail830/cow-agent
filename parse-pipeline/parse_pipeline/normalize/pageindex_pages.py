from __future__ import annotations

from typing import Any


def _layout_page_num(layout: dict[str, Any]) -> int | None:
    for key in ("pageNum", "page_num", "pageIndex", "page_index", "pageNumber", "page_number"):
        raw = layout.get(key)
        if raw is None:
            continue
        try:
            page = int(raw)
            if page > 0:
                return page
        except (TypeError, ValueError):
            continue
    return None


def _layout_markdown_chunk(layout: dict[str, Any]) -> str:
    layout_type = str(layout.get("type") or "").lower()
    if layout_type == "table":
        return "[table]"
    return str(layout.get("markdownContent") or layout.get("markdown_content") or "")


def build_pages_from_pageindex(
    content_md: str,
    pageindex: dict[str, Any] | None,
) -> list[dict[str, Any]] | None:
    """Map pageindex layouts to line ranges in final content.md."""

    if not pageindex:
        return None
    layouts = pageindex.get("layouts")
    if not isinstance(layouts, list) or not layouts:
        return None

    line_cursor = 1
    page_ranges: dict[int, dict[str, int]] = {}

    for layout in layouts:
        if not isinstance(layout, dict):
            continue
        chunk = _layout_markdown_chunk(layout)
        if not chunk:
            continue
        line_count = max(1, chunk.count("\n") + (0 if chunk.endswith("\n") else 1))
        page = _layout_page_num(layout)
        if page is None:
            line_cursor += line_count
            continue
        start = line_cursor
        end = line_cursor + line_count - 1
        line_cursor = end + 1
        existing = page_ranges.get(page)
        if existing is None:
            page_ranges[page] = {"line_start": start, "line_end": end}
        else:
            existing["line_start"] = min(existing["line_start"], start)
            existing["line_end"] = max(existing["line_end"], end)

    if not page_ranges:
        return None

    total_lines = max(1, content_md.count("\n") + (1 if content_md and not content_md.endswith("\n") else 0))
    pages: list[dict[str, Any]] = []
    for page in sorted(page_ranges):
        bounds = page_ranges[page]
        line_start = max(1, bounds["line_start"])
        line_end = min(total_lines, max(line_start, bounds["line_end"]))
        pages.append({"page": page, "line_start": line_start, "line_end": line_end})
    return pages
