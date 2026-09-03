"""Webhook trigger message rendering tests."""

from app.yl_worker2.triggers.handler import render_trigger_message
from app.yl_worker2.triggers.schemas import YlWorker2TriggerPayload


def test_render_base_inbound_delay():
    msg = render_trigger_message(
        YlWorker2TriggerPayload(
            event_type="base_inbound_delay",
            product_code="MOCK_YLP001",
            adjust_date="2026-06-30",
            site_code="MOCK_WH_B02",
            detail={"from_available_after": 3200},
        )
    )
    assert "入库延期" in msg
    assert "3200" in msg
    assert "list_pending_allocation_orders" in msg


def test_render_large_order_added():
    msg = render_trigger_message(
        YlWorker2TriggerPayload(
            event_type="large_order_added",
            product_code="MOCK_YLP001",
            adjust_date="2026-06-30",
            site_code="MOCK_WH_S07",
            detail={"order_delta": 2800},
        )
    )
    assert "追加订单" in msg
    assert "2800" in msg
