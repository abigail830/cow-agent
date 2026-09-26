"""Build gist extraction prompts from attachment content."""

from __future__ import annotations

import json
from typing import Any


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
    parts.append(
        "Extract metadata from the above document. "
        "Return JSON with keys abstract (1-2 sentences, same language as the document) "
        "and tags (array of 3 to 8 retrieval keywords, mixed language allowed)."
    )
    return "\n".join(parts)


GIST_SYSTEM_INSTRUCTIONS = (
    "Extract document metadata for attachment search. "
    "Reply with a single JSON object only — no markdown fences, no commentary. "
    "Use null only if a field were optional; abstract and tags are required when content exists. "
    'Schema: {"abstract": "string", "tags": ["string", "..."]} with 3 to 8 tags.'
)
