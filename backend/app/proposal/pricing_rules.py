"""Pricing type rules for MDM services and draft fee rows."""

from __future__ import annotations

from typing import Any

FIXED_PRICING_TYPE = "FIXED"

# Totals use price.amount; fee-table price column shows fee_raw for these types.
FEE_RAW_DISPLAY_TYPES = frozenset(
    {
        "UNIT_RATE",
        "RANGE",
        "BASE_PLUS_VARIABLE",
        "BASE_PLUS",
        "MATRIX_REF",
    }
)


def normalize_pricing_type(pricing_type: str | None) -> str:
    return str(pricing_type or FIXED_PRICING_TYPE).strip().upper() or FIXED_PRICING_TYPE


def uses_fee_raw_display(pricing_type: str | None) -> bool:
    return normalize_pricing_type(pricing_type) in FEE_RAW_DISPLAY_TYPES


def coerce_price_amount(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fee_table_amount_display(price: dict[str, Any], *, format_money) -> str | None:
    """Return the client-facing fee-table price cell text for a draft fee row price object."""
    ptype = normalize_pricing_type(price.get("pricing_type"))
    amount = coerce_price_amount(price.get("amount"))
    fee_raw = str(price.get("fee_raw") or "").strip()
    currency = str(price.get("currency") or "")

    if ptype == FIXED_PRICING_TYPE:
        if amount is None:
            return None
        return format_money(amount, currency, include_currency=bool(currency)).strip()

    if uses_fee_raw_display(ptype):
        if fee_raw:
            return fee_raw
        if amount is not None:
            return format_money(amount, currency, include_currency=bool(currency)).strip()
        return None

    if fee_raw:
        return fee_raw
    if amount is not None:
        return format_money(amount, currency, include_currency=bool(currency)).strip()
    return None
