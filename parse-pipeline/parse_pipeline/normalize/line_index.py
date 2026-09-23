from __future__ import annotations

import re
from typing import Any


def build_line_index(text: str) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]]]:
    lines = text.splitlines()
    line_count = len(lines) if text else 0
    if line_count == 0 and text:
        line_count = 1

    pages: list[dict[str, Any]] = []
    if line_count:
        pages.append({"page": 1, "line_start": 1, "line_end": max(line_count, 1)})

    sections: list[dict[str, Any]] = []
    heading_re = re.compile(r"^(#{1,6})\s+(.+)$")
    for idx, line in enumerate(lines, start=1):
        match = heading_re.match(line.strip())
        if not match:
            continue
        level = len(match.group(1))
        title = match.group(2).strip()
        sections.append(
            {
                "id": f"s{len(sections) + 1}",
                "title": title,
                "level": level,
                "line_start": idx,
                "line_end": idx,
            }
        )
    for i, section in enumerate(sections):
        next_start = sections[i + 1]["line_start"] if i + 1 < len(sections) else line_count + 1
        section["line_end"] = max(section["line_start"], next_start - 1)

    return line_count, pages, sections
