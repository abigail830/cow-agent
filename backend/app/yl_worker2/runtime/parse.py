"""Parse YL report string fields into numeric values."""

from __future__ import annotations

from decimal import Decimal


def parse_rate(value: str | float | Decimal | None) -> float | None:
    """Parse '72.0%' or numeric rate into 0.72."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        v = float(value)
        return v / 100.0 if v > 1.0 else v
    if isinstance(value, Decimal):
        v = float(value)
        return v / 100.0 if v > 1.0 else v
    text = str(value).strip().replace("%", "").replace(",", "")
    if not text:
        return None
    return float(text) / 100.0


def parse_qty(value: str | float | Decimal | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)
