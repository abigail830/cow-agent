"""Normalize MDM DB rows into payloads compatible with proposal draft materializers."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.proposal.pricing_rules import FIXED_PRICING_TYPE, coerce_price_amount, normalize_pricing_type


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, Decimal):
        return float(value)
    return coerce_price_amount(value)


def service_row_to_materializer_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Shape expected by add_package_to_proposal_draft / add_services_to_proposal_draft."""
    pricing_type = normalize_pricing_type(row.get("pricing_type"))
    amount = _optional_float(row.get("price_amount"))
    payload: dict[str, Any] = {
        "sku": str(row["sku"]),
        "service_name": _optional_str(row.get("service_name")) or str(row["sku"]),
        "description": _optional_str(row.get("description")),
        "scope_of_work": _optional_str(row.get("scope_of_work")),
        "department_team": _optional_str(row.get("department_team")),
        "pricing_type": pricing_type,
        "price_amount": amount,
        "price_currency": _optional_str(row.get("price_currency")),
        "billing_frequency": _optional_str(row.get("billing_frequency")),
        "recurring": _optional_str(row.get("recurring")),
        "fee_raw": _optional_str(row.get("fee_raw")),
        "footnotes": _optional_str(row.get("footnotes")),
    }
    semantic = _optional_str(row.get("sku_semantic_for_ai"))
    if semantic:
        payload["sku_semantic_for_ai"] = semantic
    return payload


def package_row_to_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "package_id": str(row["package_id"]),
        "package_name": _optional_str(row.get("package_name")) or str(row["package_id"]),
    }
    semantic = _optional_str(row.get("package_semantic_for_ai"))
    if semantic:
        payload["package_semantic_for_ai"] = semantic
    return payload


def pricing_warnings(service: dict[str, Any]) -> list[str]:
    """Human-readable hints when catalog data may need sales input before materialize."""
    sku = str(service.get("sku") or "")
    pricing_type = normalize_pricing_type(service.get("pricing_type"))
    amount = coerce_price_amount(service.get("price_amount"))
    fee_raw = str(service.get("fee_raw") or "").strip()
    warnings: list[str] = []

    if pricing_type == FIXED_PRICING_TYPE and amount is None:
        warnings.append(f"{sku}: FIXED pricing but price_amount is missing.")
    elif pricing_type != FIXED_PRICING_TYPE and not fee_raw and amount is None:
        warnings.append(
            f"{sku}: {pricing_type} pricing needs fee_raw and/or price_amount before fee table display."
        )
    return warnings
