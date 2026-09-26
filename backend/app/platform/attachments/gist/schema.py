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


def _extract_json_object(raw: str) -> str:
    text = _strip_json_fence(raw)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    return text


def _normalize_tags(tags_raw: object) -> list[str]:
    tags: list[str] = []
    if isinstance(tags_raw, str):
        for part in re.split(r"[,;|]", tags_raw):
            piece = part.strip()
            if piece:
                tags.append(piece)
        return tags
    if isinstance(tags_raw, list):
        for item in tags_raw:
            if isinstance(item, str) and item.strip():
                tags.append(item.strip())
    return tags


def parse_gist_metadata(raw: str) -> AttachmentGistMetadata | None:
    try:
        payload = json.loads(_extract_json_object(raw))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    abstract = payload.get("abstract")
    if not isinstance(abstract, str) or not abstract.strip():
        return None
    tags = _normalize_tags(payload.get("tags"))
    if len(tags) > 8:
        tags = tags[:8]
    return AttachmentGistMetadata(abstract=abstract.strip(), tags=tuple(tags))
