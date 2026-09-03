"""Entity mention matching and resolution scoring (no DB)."""

from __future__ import annotations

import re
from typing import Any


def normalize_mention(text: str) -> str:
    s = (text or "").strip().lower()
    for suffix in ("销售仓", "基地仓", "分仓", "仓库", "仓"):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()
            break
    return s


def _field_hit(mention: str, value: str | None, *, exact_weight: float, contains_weight: float) -> tuple[float, str | None]:
    if not value:
        return 0.0, None
    raw = str(value).strip()
    low = raw.lower()
    norm = normalize_mention(mention)
    if not norm:
        return 0.0, None
    if low == norm or raw == mention.strip():
        return exact_weight, "exact"
    if norm in low or low in norm:
        return contains_weight, "contains"
    return 0.0, None


def score_product_row(mention: str, row: dict[str, Any]) -> tuple[float, str]:
    norm = normalize_mention(mention)
    scores: list[tuple[float, str]] = []
    for field, exact_w, contains_w in (
        ("product_code", 1.0, 0.92),
        ("product_name", 0.98, 0.88),
        ("trade_name", 0.95, 0.85),
        ("brand", 0.9, 0.8),
        ("pro_series", 0.88, 0.82),
    ):
        w, method = _field_hit(norm, row.get(field), exact_weight=exact_w, contains_weight=contains_w)
        if w and method:
            scores.append((w, f"product.{field}_{method}"))
    if not scores:
        return 0.0, "product.no_match"
    scores.sort(key=lambda x: x[0], reverse=True)
    return scores[0]


def score_warehouse_row(mention: str, row: dict[str, Any]) -> tuple[float, str]:
    norm = normalize_mention(mention)
    scores: list[tuple[float, str]] = []
    for field, exact_w, contains_w in (
        ("site_code", 1.0, 0.92),
        ("site_name", 0.98, 0.9),
        ("site_desc", 0.85, 0.78),
    ):
        w, method = _field_hit(norm, row.get(field), exact_weight=exact_w, contains_weight=contains_w)
        if w and method:
            scores.append((w, f"warehouse.{field}_{method}"))
    if not scores:
        return 0.0, "warehouse.no_match"
    scores.sort(key=lambda x: x[0], reverse=True)
    return scores[0]


def build_resolution(
    entity_type: str,
    mention: str,
    ranked: list[dict[str, Any]],
    *,
    id_key: str,
    display_key: str,
    min_confidence: float = 0.75,
    ambiguous_gap: float = 0.08,
) -> dict[str, Any]:
    candidates = [
        {
            "id": r[id_key],
            "display_name": r.get(display_key) or r[id_key],
            "confidence": round(float(r["confidence"]), 4),
            "match_method": r["match_method"],
            **{k: v for k, v in r.items() if k not in ("confidence", "match_method")},
        }
        for r in ranked
        if r.get("confidence", 0) >= min_confidence * 0.5
    ]
    candidates = candidates[:10]

    if not candidates:
        return {
            "entity_type": entity_type,
            "mention": mention,
            "status": "not_found",
            "resolved_id": None,
            "display_name": None,
            "confidence": 0.0,
            "candidates": [],
            "applied_rule": "resolve.not_found",
        }

    top = candidates[0]
    second_conf = candidates[1]["confidence"] if len(candidates) > 1 else 0.0
    ambiguous = (
        len(candidates) > 1
        and top["confidence"] >= min_confidence
        and second_conf >= min_confidence
        and (top["confidence"] - second_conf) < ambiguous_gap
    )

    if top["confidence"] < min_confidence:
        status = "ambiguous" if len(candidates) > 1 else "not_found"
    elif ambiguous:
        status = "ambiguous"
    else:
        status = "resolved"

    return {
        "entity_type": entity_type,
        "mention": mention,
        "status": status,
        "resolved_id": top["id"] if status == "resolved" else None,
        "display_name": top["display_name"] if status == "resolved" else None,
        "confidence": top["confidence"],
        "candidates": candidates,
        "applied_rule": top["match_method"] if status == "resolved" else "resolve.ambiguous"
        if status == "ambiguous"
        else "resolve.below_threshold",
    }


_SITE_TYPE_MAP = {"base": 0, "sales": 1, "基地": 0, "基地仓": 0, "销售": 1, "销售仓": 1}


def parse_site_type_hint(value: str | None) -> int | None:
    if value is None:
        return None
    key = value.strip().lower()
    if key in _SITE_TYPE_MAP:
        return _SITE_TYPE_MAP[key]
    if re.search(r"基地", value):
        return 0
    if re.search(r"销售", value):
        return 1
    return None
