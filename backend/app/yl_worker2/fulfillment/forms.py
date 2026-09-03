"""Build and validate fulfillment branch-replenishment form drafts."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

from app.yl_worker2.db import parse_adjust_date, yl_connect
from app.yl_worker2.fulfillment.warehouse_labels import to_logic_warehouse_label

_ALLOC_TYPE = Literal["forward", "lateral"]
_FORM_STATUS = Literal["editing", "confirmed", "rejected", "activated"]

# Fields accepted by POST /fulfillment/branch-replenishment (editable in UI).
PAYLOAD_REQUIRED = frozenset(
    {
        "product_code",
        "business_unit",
        "initial_ship_warehouse",
        "outbound_logic_warehouse",
        "inbound_logic_warehouse",
        "transfer_qty",
        "planned_ship_at",
        "expected_arrival_at",
    }
)
PAYLOAD_OPTIONAL = frozenset(
    {
        "sku_code",
        "merchant_order_no",
        "source_order_no",
        "transit_warehouse",
        "shipping_remark",
        "temp_zone",
    }
)
PAYLOAD_ALL_KEYS = PAYLOAD_REQUIRED | PAYLOAD_OPTIONAL


def _default_ship_times(adjust_date: str) -> tuple[str, str]:
    base = parse_adjust_date(adjust_date)
    if isinstance(base, date):
        d = base
    else:
        d = datetime.now(timezone.utc).date()
    planned = datetime(d.year, d.month, d.day, 8, 0, 0, tzinfo=timezone.utc) + timedelta(days=5)
    arrival = planned + timedelta(days=2)
    return planned.isoformat().replace("+00:00", "Z"), arrival.isoformat().replace("+00:00", "Z")


def _fingerprint(payload: dict[str, Any], context: dict[str, Any]) -> str:
    blob = json.dumps({"payload": payload, "context": context}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


async def _lookup_warehouse(conn, site_code: str) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        "SELECT site_code, site_name, site_type FROM yl_warehouse WHERE site_code = $1 LIMIT 1",
        site_code,
    )
    return dict(row) if row else None


async def _lookup_product(conn, product_code: str) -> dict[str, Any] | None:
    row = await conn.fetchrow(
        "SELECT product_code, product_name, business FROM yl_product WHERE product_code = $1 LIMIT 1",
        product_code,
    )
    return dict(row) if row else None


def _warehouse_triplet(
    from_label: str,
    to_label: str,
    allocation_type: str,
) -> tuple[str, str, str]:
    """Return initial_ship, outbound, inbound logic warehouse labels."""
    if allocation_type == "forward":
        return from_label, from_label, to_label
    return from_label, from_label, to_label


async def build_fulfillment_form(
    *,
    product_code: str,
    adjust_date: str,
    allocation_type: _ALLOC_TYPE,
    from_site_code: str,
    to_site_code: str,
    transfer_qty: float,
    reason: str,
    business_unit: str | None = None,
    source_order_no: str | None = None,
    shipping_remark: str | None = None,
    planned_ship_at: str | None = None,
    expected_arrival_at: str | None = None,
    transit_warehouse: str = "-",
    temp_zone: str = "常温",
    merchant_order_no: str | None = None,
    simulation: dict[str, Any] | None = None,
    summary: str = "",
) -> dict[str, Any]:
    if transfer_qty <= 0:
        raise ValueError("transfer_qty must be > 0")

    conn = await yl_connect()
    try:
        prod = await _lookup_product(conn, product_code)
        from_wh = await _lookup_warehouse(conn, from_site_code)
        to_wh = await _lookup_warehouse(conn, to_site_code)
    finally:
        await conn.close()

    from_label = to_logic_warehouse_label(from_wh["site_name"] if from_wh else from_site_code)
    to_label = to_logic_warehouse_label(to_wh["site_name"] if to_wh else to_site_code)
    initial, outbound, inbound = _warehouse_triplet(from_label, to_label, allocation_type)

    ship_at, arrive_at = _default_ship_times(adjust_date)
    if planned_ship_at:
        ship_at = planned_ship_at
    if expected_arrival_at:
        arrive_at = expected_arrival_at

    bu = business_unit or (prod.get("business") if prod else None) or "成人营养品事业部"
    remark = shipping_remark if shipping_remark is not None else (reason or None)

    payload: dict[str, Any] = {
        "product_code": product_code,
        "business_unit": bu,
        "initial_ship_warehouse": initial,
        "outbound_logic_warehouse": outbound,
        "inbound_logic_warehouse": inbound,
        "transfer_qty": float(transfer_qty),
        "planned_ship_at": ship_at,
        "expected_arrival_at": arrive_at,
        "sku_code": product_code,
        "transit_warehouse": transit_warehouse or "-",
        "temp_zone": temp_zone or "常温",
    }
    if merchant_order_no:
        payload["merchant_order_no"] = merchant_order_no
    if source_order_no:
        payload["source_order_no"] = source_order_no
    if remark:
        payload["shipping_remark"] = remark

    context: dict[str, Any] = {
        "allocation_type": allocation_type,
        "from_site_code": from_site_code,
        "to_site_code": to_site_code,
        "from_site_name": from_wh.get("site_name") if from_wh else from_site_code,
        "to_site_name": to_wh.get("site_name") if to_wh else to_site_code,
        "adjust_date": adjust_date,
        "reason": reason,
        "product_name": prod.get("product_name") if prod else product_code,
        "summary": summary,
    }
    if simulation:
        context["simulation"] = simulation

    form_id = str(uuid.uuid4())
    return {
        "form_id": form_id,
        "status": "editing",
        "payload": payload,
        "context": context,
        "fingerprint": _fingerprint(payload, context),
        "fulfillment_item": None,
        "confirmed_at": None,
    }


def merge_payload_patch(form: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    if form.get("status") not in ("editing",):
        raise ValueError(f"form not editable: {form.get('status')}")
    payload = dict(form.get("payload") or {})
    for key, val in patch.items():
        if key not in PAYLOAD_ALL_KEYS:
            raise ValueError(f"field not allowed in payload patch: {key}")
        if val is None:
            payload.pop(key, None)
        else:
            payload[key] = val
    missing = PAYLOAD_REQUIRED - set(payload.keys())
    if missing:
        raise ValueError(f"payload missing required fields: {sorted(missing)}")
    if float(payload.get("transfer_qty") or 0) <= 0:
        raise ValueError("transfer_qty must be > 0")
    out = dict(form)
    out["payload"] = payload
    context = dict(form.get("context") or {})
    out["fingerprint"] = _fingerprint(payload, context)
    return out


def build_create_body(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip to keys accepted by fulfillment create API."""
    body: dict[str, Any] = {}
    for key in PAYLOAD_ALL_KEYS:
        if key in payload and payload[key] is not None and payload[key] != "":
            body[key] = payload[key]
    for req in PAYLOAD_REQUIRED:
        if req not in body:
            raise ValueError(f"missing required field: {req}")
    return body
