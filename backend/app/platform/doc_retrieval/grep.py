"""Line grep over parsed content.md."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GrepMatch:
    line: int
    text: str


def grep_content(
    content: str,
    pattern: str,
    *,
    ignore_case: bool = True,
    head_limit: int = 50,
) -> list[GrepMatch]:
    if not pattern.strip():
        return []
    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error:
        regex = re.compile(re.escape(pattern), flags)

    lines = content.splitlines()
    matches: list[GrepMatch] = []
    for idx, line in enumerate(lines, start=1):
        if not regex.search(line):
            continue
        matches.append(GrepMatch(line=idx, text=line))
        if len(matches) >= head_limit:
            break
    return matches


def grep_matches_to_dict(matches: list[GrepMatch]) -> list[dict[str, Any]]:
    return [{"line": match.line, "text": match.text} for match in matches]
