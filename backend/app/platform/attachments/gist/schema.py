"""Structured gist LLM output."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AttachmentGistMetadata:
    abstract: str
    tags: tuple[str, ...]

    def to_gist_text(self, *, max_len: int = 2000) -> str:
        abstract = self.abstract.strip()
        tag_part = ", ".join(t for t in self.tags if t.strip())
        if tag_part:
            text = f"{abstract} | {tag_part}" if abstract else tag_part
        else:
            text = abstract
        text = text.strip()
        if len(text) > max_len:
            return text[: max_len - 1].rstrip() + "…"
        return text


def _strip_json_fence(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, count=1, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def parse_gist_metadata(raw: str) -> AttachmentGistMetadata | None:
    try:
        payload = json.loads(_strip_json_fence(raw))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    abstract = payload.get("abstract")
    if not isinstance(abstract, str) or not abstract.strip():
        return None
    tags_raw = payload.get("tags")
    tags: list[str] = []
    if isinstance(tags_raw, list):
        for item in tags_raw:
            if isinstance(item, str) and item.strip():
                tags.append(item.strip())
    if len(tags) < 3:
        return None
    if len(tags) > 8:
        tags = tags[:8]
    return AttachmentGistMetadata(abstract=abstract.strip(), tags=tuple(tags))
