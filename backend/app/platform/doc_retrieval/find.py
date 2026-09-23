"""Fuzzy attachment lookup within chat library."""

from __future__ import annotations

import re
from typing import Any

from app.platform.doc_retrieval.context import ChatAttachmentIndexEntry


def _tokens(query: str) -> list[str]:
    return [token for token in re.split(r"\W+", query.lower()) if len(token) >= 2]


def _score_entry(entry: ChatAttachmentIndexEntry, tokens: list[str]) -> float:
    if not tokens:
        return 0.0
    haystacks = [
        entry.filename.lower(),
        (entry.gist or "").lower(),
        " ".join(entry.section_titles).lower(),
        entry.kind.lower(),
    ]
    blob = " ".join(haystacks)
    score = 0.0
    for token in tokens:
        if token in entry.filename.lower():
            score += 3.0
        if token in blob:
            score += 1.0
    if entry.attachment_id in blob:
        score += 0.5
    return score


def find_attachments(
    library: dict[str, ChatAttachmentIndexEntry],
    query: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    tokens = _tokens(query)
    if not tokens:
        return []

    ranked: list[tuple[float, ChatAttachmentIndexEntry]] = []
    for entry in library.values():
        score = _score_entry(entry, tokens)
        if score <= 0:
            continue
        ranked.append((score, entry))

    ranked.sort(key=lambda item: (-item[0], item[1].filename))
    results: list[dict[str, Any]] = []
    for score, entry in ranked[:limit]:
        results.append(
            {
                "attachment_id": entry.attachment_id,
                "filename": entry.filename,
                "kind": entry.kind,
                "mime_type": entry.mime_type,
                "page_count": entry.page_count,
                "line_count": entry.line_count,
                "figure_count": entry.figure_count,
                "score": round(score, 2),
            }
        )
    return results
