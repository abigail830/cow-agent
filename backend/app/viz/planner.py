"""Rule-based chart type selection from SQL result shape."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from app.viz.spec import VizIntent, VizKind

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")
_TIME_HINTS = frozenset(
    {
        "date",
        "day",
        "week",
        "month",
        "created_at",
        "chat_created_at",
        "analysis_date",
        "period",
        "bucket",
        "week_start",
    }
)
_LABEL_HINTS = frozenset({"name", "label", "title", "theme", "region", "service", "intent", "category"})


def _is_date_like(value: Any) -> bool:
    if isinstance(value, (date, datetime)):
        return True
    if isinstance(value, str) and _DATE_RE.match(value[:10]):
        return True
    return False


def _is_numeric(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True
    if isinstance(value, str):
        try:
            float(value)
            return True
        except ValueError:
            return False
    return False


def _column_kind(name: str, sample_values: list[Any]) -> str:
    lower = name.lower()
    if any(h in lower for h in _TIME_HINTS) or any(_is_date_like(v) for v in sample_values[:5]):
        return "time"
    if any(h in lower for h in _LABEL_HINTS):
        return "label"
    numeric_hits = sum(1 for v in sample_values[:8] if _is_numeric(v))
    if numeric_hits >= max(1, len(sample_values[:8]) // 2):
        return "numeric"
    return "other"


def _profile_columns(
    rows: list[dict[str, Any]], columns: list[str]
) -> dict[str, str]:
    profile: dict[str, str] = {}
    for col in columns:
        samples = [row.get(col) for row in rows[:20]]
        profile[col] = _column_kind(col, samples)
    return profile


def suggest_kind(
    rows: list[dict[str, Any]],
    columns: list[str],
    *,
    intent: VizIntent = "auto",
) -> VizKind | None:
    if intent == "none":
        return None
    if not rows or not columns:
        return None

    if intent == "detail":
        return "table" if len(rows) > 1 else "list"
    if intent == "matrix":
        return "heatmap"
    if intent == "ranking":
        return "bar"
    if intent == "trend":
        return "line"

    profile = _profile_columns(rows, columns)
    time_cols = [c for c, k in profile.items() if k == "time"]
    numeric_cols = [c for c, k in profile.items() if k == "numeric"]
    label_cols = [c for c, k in profile.items() if k == "label"]
    other_cols = [c for c, k in profile.items() if k == "other"]

    # Matrix: 2 categorical + 1 numeric (pivot-friendly)
    if len(numeric_cols) == 1 and len(label_cols) >= 2:
        return "heatmap"
    if len(numeric_cols) == 1 and len(other_cols) >= 2 and len(columns) == 3:
        return "heatmap"

    # Time series
    if time_cols and numeric_cols:
        if len(numeric_cols) >= 2:
            return "combo"
        return "line"

    # Ranking: one label + one numeric
    if len(numeric_cols) >= 1 and (label_cols or other_cols):
        return "bar"

    if len(rows) <= 25 and len(columns) <= 8:
        return "table"

    return "table" if rows else None
