"""Map markdown figure refs (hash filenames, etc.) to stored figure ids via meta.json."""

from __future__ import annotations

import json
import re
from typing import Any

_HASH_STEM_RE = re.compile(r"^[a-f0-9]{32,64}$", re.IGNORECASE)
_FIGURE_ID_RE = re.compile(r"^f\d+$")


def strip_figure_ref(raw: str) -> str:
    ref = raw.strip()
    if not ref:
        return ref
    if "?" in ref:
        ref = ref.split("?", 1)[0]
    if "#" in ref:
        ref = ref.split("#", 1)[0]
    if "/" in ref or "\\" in ref:
        ref = ref.rsplit("/", 1)[-1]
        ref = ref.rsplit("\\", 1)[-1]
    if "." in ref:
        ref = ref.rsplit(".", 1)[0]
    return ref


def parse_meta_figures(meta: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not meta:
        return []
    figures = meta.get("figures")
    if not isinstance(figures, list):
        return []
    return [fig for fig in figures if isinstance(fig, dict)]


def resolve_figure_storage_id(raw: str, meta: dict[str, Any] | None) -> str:
    """Resolve API figure ref to blob storage id (usually fN, sometimes hash stem)."""
    stem = strip_figure_ref(raw)
    if not stem:
        raise ValueError(f"invalid figure id: {raw!r}")
    if _FIGURE_ID_RE.match(stem):
        return stem

    if not _HASH_STEM_RE.match(stem):
        raise ValueError(f"invalid figure id: {raw!r}")

    stem_lower = stem.lower()
    for fig in parse_meta_figures(meta):
        figure_id = str(fig.get("id") or "").strip()
        if not figure_id:
            continue
        sha256 = str(fig.get("sha256") or "").lower()
        filename = str(fig.get("filename") or "").lower()
        alt = str(fig.get("alt") or "").lower()
        source_ref = str(fig.get("source_ref") or "").lower()
        if (
            sha256.startswith(stem_lower)
            or stem_lower in filename
            or filename.startswith(stem_lower)
            or stem_lower in alt
            or source_ref == stem_lower
            or source_ref.startswith(stem_lower)
        ):
            return figure_id

    return stem


def figure_id_for_markdown_line(meta: dict[str, Any] | None, line_no: int) -> str | None:
    for fig in parse_meta_figures(meta):
        line = fig.get("line")
        figure_id = str(fig.get("id") or "").strip()
        if figure_id and line == line_no:
            return figure_id
    return None


def load_parsed_meta_json(meta_bytes: bytes | None) -> dict[str, Any] | None:
    if not meta_bytes:
        return None
    try:
        parsed = json.loads(meta_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None
