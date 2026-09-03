"""Load ontology_sources.yaml and ontology_refs.yaml from agents/yl-worker2."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.platform.profile_loader import AGENTS_ROOT

_AGENT_DIR = AGENTS_ROOT / "yl-worker2"
_SOURCES_FILE = _AGENT_DIR / "ontology_sources.yaml"
_REFS_FILE = _AGENT_DIR / "ontology_refs.yaml"

_DIMENSION_SUFFIXES = (
    "product_code",
    "site_code",
    "from_site_code",
    "to_site_code",
    "adjust_date",
    "snapshot_date",
    "ds",
    "plan_year",
    "plan_month",
    "sell_year",
    "sell_month",
)

# Semantic column names used by tools → physical columns on specific tables.
_TABLE_COLUMN_ALIASES: dict[str, dict[str, str]] = {
    "yl_sales_warehouse_inventory_report": {
        "site_code": "from_site_code",
    },
    "warehouse_sku_inventory": {
        "product_code": "sku_code",
        "site_code": "warehouse_code",
        "adjust_date": "snapshot_date",
        "plan_num": "monthly_sales_plan",
        "store_num": "spot_inventory",
        "store_transit": "in_transit_inventory",
        "stock_rate_before": "current_stock_rate",
        "big_date_num": "aging_inventory_qty",
    },
}


@lru_cache(maxsize=1)
def load_sources_config() -> dict[str, Any]:
    if not _SOURCES_FILE.is_file():
        return {
            "include_tables": ["yl_%"],
            "exclude_tables": [],
            "default_limit": 100,
            "max_limit": 500,
        }
    raw = yaml.safe_load(_SOURCES_FILE.read_text(encoding="utf-8")) or {}
    return {
        "include_tables": list(raw.get("include_tables") or ["yl_%"]),
        "exclude_tables": list(raw.get("exclude_tables") or []),
        "default_limit": int(raw.get("default_limit") or 100),
        "max_limit": int(raw.get("max_limit") or 500),
    }


def clear_ontology_config_cache() -> None:
    load_sources_config.cache_clear()
    load_refs_config.cache_clear()


def _sql_like_match(name: str, pattern: str) -> bool:
    """Match table name against SQL LIKE pattern (% = any, _ = one char)."""
    parts: list[str] = []
    for ch in pattern.lower():
        if ch == "%":
            parts.append(".*")
        elif ch == "_":
            parts.append(".")
        else:
            parts.append(re.escape(ch))
    regex = "^" + "".join(parts) + "$"
    return re.match(regex, name.lower()) is not None


def table_allowed(table_name: str) -> bool:
    name = (table_name or "").strip().lower()
    if not name:
        return False
    cfg = load_sources_config()
    excluded = {t.lower() for t in cfg["exclude_tables"]}
    if name in excluded:
        return False
    includes = cfg["include_tables"]
    return any(_sql_like_match(name, pat) for pat in includes)


def suggest_dimensions(column_names: list[str]) -> list[str]:
    cols = set(column_names)
    dims: list[str] = []
    for key in _DIMENSION_SUFFIXES:
        if key in cols:
            dims.append(key)
    for col in sorted(cols):
        if col.endswith("_code") and col not in dims:
            dims.append(col)
    return dims


@lru_cache(maxsize=1)
def load_refs_config() -> dict[str, Any]:
    if not _REFS_FILE.is_file():
        return {"refs": [], "patterns": []}
    raw = yaml.safe_load(_REFS_FILE.read_text(encoding="utf-8")) or {}
    refs: list[dict[str, Any]] = []
    for item in raw.get("refs") or []:
        if isinstance(item, dict) and item.get("column"):
            refs.append(dict(item))
    patterns: list[dict[str, Any]] = []
    for item in raw.get("patterns") or []:
        if isinstance(item, dict) and item.get("match"):
            patterns.append(dict(item))
    return {"refs": refs, "patterns": patterns}


def get_table_column_aliases(
    table_name: str,
    allowed_columns: set[str] | list[str],
) -> dict[str, str]:
    """Return semantic alias → physical column for a table."""
    allowed = set(allowed_columns)
    aliases = _TABLE_COLUMN_ALIASES.get((table_name or "").strip().lower(), {})
    return {
        semantic: actual
        for semantic, actual in aliases.items()
        if semantic not in allowed and actual in allowed
    }


def resolve_table_column(
    table_name: str,
    column: str,
    allowed_columns: set[str],
    *,
    column_aliases: dict[str, str] | None = None,
) -> str:
    col = (column or "").strip()
    if col in allowed_columns:
        return col
    aliases = column_aliases or get_table_column_aliases(table_name, allowed_columns)
    mapped = aliases.get(col)
    if mapped and mapped in allowed_columns:
        return mapped
    return col


def resolve_ref_rule(column: str) -> dict[str, Any] | None:
    col = (column or "").strip()
    if not col:
        return None
    cfg = load_refs_config()
    for item in cfg["refs"]:
        if item.get("column") == col:
            return item
    for item in cfg["patterns"]:
        pattern = str(item.get("match") or "")
        if pattern and re.match(pattern, col):
            return item
    return None
