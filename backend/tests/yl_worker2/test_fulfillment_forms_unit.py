"""Unit tests for fulfillment form payload building."""

import pytest

from app.yl_worker2.fulfillment.forms import build_create_body, merge_payload_patch


def _sample_form() -> dict:
    payload = {
        "product_code": "MOCK_YLP001",
        "business_unit": "成人营养品事业部",
        "initial_ship_warehouse": "天津基地仓一盘货仓",
        "outbound_logic_warehouse": "天津基地仓一盘货仓",
        "inbound_logic_warehouse": "郑州销售仓一盘货仓",
        "transfer_qty": 1200,
        "planned_ship_at": "2026-07-13T08:00:00Z",
        "expected_arrival_at": "2026-07-15T08:00:00Z",
        "temp_zone": "常温",
        "transit_warehouse": "-",
    }
    context = {"from_site_code": "MOCK_WH_B02", "to_site_code": "MOCK_WH_S04"}
    return {
        "form_id": "f1",
        "status": "editing",
        "payload": payload,
        "context": context,
        "fingerprint": "abc",
    }


def test_build_create_body_required_only():
    body = build_create_body(_sample_form()["payload"])
    assert body["product_code"] == "MOCK_YLP001"
    assert body["transfer_qty"] == 1200
    assert "initial_ship_warehouse" in body


def test_merge_payload_patch_updates_qty():
    form = _sample_form()
    updated = merge_payload_patch(form, {"transfer_qty": 1600})
    assert updated["payload"]["transfer_qty"] == 1600
    assert updated["fingerprint"] != form["fingerprint"]


def test_merge_payload_patch_rejects_unknown_field():
    with pytest.raises(ValueError, match="not allowed"):
        merge_payload_patch(_sample_form(), {"unknown_field": 1})


def test_merge_payload_patch_rejects_non_editing():
    form = _sample_form()
    form["status"] = "activated"
    with pytest.raises(ValueError, match="not editable"):
        merge_payload_patch(form, {"transfer_qty": 100})
