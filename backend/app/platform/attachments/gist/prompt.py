"""Build gist extraction prompts from attachment content."""

from __future__ import annotations

import json
from typing import Any

# Shown in system + user prompts so models copy this shape (not document-specific content).
GIST_OUTPUT_EXAMPLE = (
    '{"abstract": "BVI company formation proposal for a listed client, covering fees and timeline.", '
    '"tags": ["BVI", "company formation", "proposal", "fees", "timeline"]}'
)


def truncate_markdown_for_gist(content: str, *, max_chars: int) -> str:
    if max_chars <= 0:
        return ""
    text = content or ""
    if len(text) <= max_chars:
        return text
    marker = "\n\n[… truncated …]\n\n"
    if max_chars <= len(marker) + 20:
        return text[:max_chars]
    head = (max_chars - len(marker)) // 2
    tail = max_chars - len(marker) - head
    return f"{text[:head]}{marker}{text[-tail:]}"


def section_titles_from_meta(meta: dict[str, Any] | None, *, limit: int = 5) -> tuple[str, ...]:
    if not meta:
        return ()
    sections = meta.get("sections")
    if not isinstance(sections, list):
        return ()
    titles: list[str] = []
    for section in sections[:limit]:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or "").strip()
        if title:
            titles.append(title)
    return tuple(titles)


def build_gist_user_prompt(
    *,
    filename: str,
    mime_type: str,
    markdown: str,
    section_titles: tuple[str, ...] = (),
) -> str:
    parts = [
        f"Filename: {filename}",
        f"MIME type: {mime_type}",
    ]
    if section_titles:
        parts.append(f"Section headings: {json.dumps(list(section_titles), ensure_ascii=False)}")
    parts.append("Document:")
    parts.append("---")
    parts.append(markdown)
    parts.append("---")
    parts.extend(
        [
            "Task: extract search metadata for this document.",
            "Rules:",
            "- abstract: 1–2 sentences; same primary language as the document; no filename repetition alone.",
            "- tags: JSON array of 1–8 short keywords or phrases (topics, entities, doc type); not full sentences.",
            "- Output: one JSON object only, same keys as the example (no markdown fences, no extra text).",
            f"Example shape: {GIST_OUTPUT_EXAMPLE}",
        ]
    )
    return "\n".join(parts)


GIST_SYSTEM_INSTRUCTIONS = (
    "You extract attachment metadata for keyword search in a chat document library.\n"
    "Output rules:\n"
    "1. Reply with exactly one JSON object — no prose before/after, no ``` fences.\n"
    '2. Required keys: "abstract" (string), "tags" (array of strings).\n'
    "3. abstract: 1–2 sentences summarizing what the document is about; match the document's language.\n"
    "4. tags: 1–8 distinct retrieval keywords (company names, jurisdictions, doc types, topics).\n"
    "5. Do not invent facts absent from the document; if content is empty, use abstract "
    '"Empty or unreadable document." and tags ["unknown"].\n'
    f"Valid example:\n{GIST_OUTPUT_EXAMPLE}"
)
