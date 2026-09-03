"""Configurable entity aliases for yl-worker2 resolution (YAML SSOT)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.platform.profile_loader import AGENTS_ROOT
from app.yl_worker2.runtime.entity_resolver import normalize_mention, parse_site_type_hint

_ALIAS_FILE = AGENTS_ROOT / "yl-worker2" / "entity_aliases.yaml"
_ALIAS_CONFIDENCE = 0.99


def _normalize_alias_key(text: str) -> str:
    return normalize_mention(text)


def _expand_alias_entries(item: dict[str, Any]) -> list[dict[str, Any]]:
    entity_type = str(item.get("entity_type") or "").strip()
    entity_id = str(item.get("entity_id") or "").strip()
    if not entity_type or not entity_id:
        return []

    context = item.get("context") or {}
    shared = {"entity_type": entity_type, "entity_id": entity_id, "context": context}

    # v2: one entity → many aliases
    aliases = item.get("aliases")
    if isinstance(aliases, list):
        out: list[dict[str, Any]] = []
        for alias in aliases:
            text = str(alias or "").strip()
            if not text:
                continue
            out.append(
                {
                    **shared,
                    "alias": text,
                    "alias_key": _normalize_alias_key(text),
                }
            )
        return out

    # v1 fallback: one row per alias
    alias = str(item.get("alias") or "").strip()
    if not alias:
        return []
    return [{**shared, "alias": alias, "alias_key": _normalize_alias_key(alias)}]


@lru_cache(maxsize=1)
def load_entity_aliases() -> list[dict[str, Any]]:
    if not _ALIAS_FILE.is_file():
        return []
    raw = yaml.safe_load(_ALIAS_FILE.read_text(encoding="utf-8")) or {}
    groups = raw.get("entities") or raw.get("aliases") or []
    out: list[dict[str, Any]] = []
    for item in groups:
        if isinstance(item, dict):
            out.extend(_expand_alias_entries(item))
    return out


def clear_alias_cache() -> None:
    load_entity_aliases.cache_clear()


def _entity_type_matches(entry_type: str, requested: str) -> bool:
    et = requested.strip().lower()
    entry = entry_type.strip().lower()
    if et in ("productsku", "product", "sku"):
        return entry in ("productsku", "product", "sku")
    if et in ("warehouse", "site"):
        return entry in ("warehouse", "site")
    return entry == et


def _context_matches(entry_context: dict[str, Any], site_type: str | None) -> bool:
    if not entry_context:
        return True
    hint = entry_context.get("site_type")
    if hint is None:
        return True
    if site_type is None:
        return True
    expected = parse_site_type_hint(str(hint))
    actual = parse_site_type_hint(site_type)
    if expected is None:
        return True
    return actual == expected


def match_aliases(
    mention: str,
    entity_type: str,
    *,
    site_type: str | None = None,
) -> list[dict[str, Any]]:
    raw_key = (mention or "").strip().lower()
    norm_key = _normalize_alias_key(mention)
    if not raw_key and not norm_key:
        return []

    raw_hits: list[dict[str, Any]] = []
    norm_hits: list[dict[str, Any]] = []
    for entry in load_entity_aliases():
        if not _entity_type_matches(entry["entity_type"], entity_type):
            continue
        if not _context_matches(entry.get("context") or {}, site_type):
            continue
        alias_raw = entry["alias"].strip().lower()
        hit = {
            "entity_type": entry["entity_type"],
            "entity_id": entry["entity_id"],
            "alias": entry["alias"],
            "confidence": _ALIAS_CONFIDENCE,
            "match_method": "alias.exact",
        }
        if alias_raw == raw_key:
            raw_hits.append(hit)
        elif entry["alias_key"] == norm_key and norm_key:
            norm_hits.append(hit)

    hits = raw_hits or norm_hits
    deduped: dict[str, dict[str, Any]] = {}
    for hit in hits:
        deduped[hit["entity_id"]] = hit
    return list(deduped.values())
