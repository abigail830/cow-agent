"""Structured outline from meta.json (+ optional pageindex summary)."""

from __future__ import annotations

from typing import Any


def list_sections(meta: dict[str, Any], pageindex: dict[str, Any] | None = None) -> dict[str, Any]:
    sections = meta.get("sections") or []
    pages = meta.get("pages") or []
    figures = meta.get("figures") or []
    layout_count = 0
    if pageindex and isinstance(pageindex.get("layouts"), list):
        layout_count = len(pageindex["layouts"])

    figure_summaries: list[dict[str, Any]] = []
    if isinstance(figures, list):
        for fig in figures:
            if not isinstance(fig, dict):
                continue
            figure_summaries.append(
                {
                    "id": fig.get("id"),
                    "line": fig.get("line"),
                    "alt": fig.get("alt"),
                    "mime": fig.get("mime"),
                }
            )

    return {
        "sections": sections,
        "pages": pages,
        "figures": figure_summaries,
        "pageindex_layout_count": layout_count,
        "line_count": meta.get("line_count"),
        "page_count": meta.get("page_count"),
        "warnings": meta.get("warnings") or [],
    }
