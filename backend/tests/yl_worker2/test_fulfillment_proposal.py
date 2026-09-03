"""Integration test for propose_fulfillment_forms (requires YL DB)."""

import pytest

from app.yl_worker2.fulfillment.context import init_run_fulfillment_forms_state
from app.yl_worker2.tools.fulfillment_proposal import propose_fulfillment_forms
from tests.yl_worker2.conftest import (
    MOCK_BASE_TIANJIN,
    MOCK_PRODUCT,
    MOCK_SITE_ZHENGZHOU,
    MOCK_SNAPSHOT_DATE,
    requires_yl_db,
)


@pytest.mark.asyncio
@requires_yl_db
async def test_propose_fulfillment_forms_single_forward():
    init_run_fulfillment_forms_state()
    result = await propose_fulfillment_forms(
        product_code=MOCK_PRODUCT,
        adjust_date=MOCK_SNAPSHOT_DATE,
        lines=[
            {
                "allocation_type": "forward",
                "from_site_code": MOCK_BASE_TIANJIN,
                "to_site_code": MOCK_SITE_ZHENGZHOU,
                "transfer_qty": 1600,
                "reason": "郑州仓补调测试",
            }
        ],
        summary="测试提案",
    )
    assert result["status"] == "proposed"
    assert result["count"] == 1
    form = result["forms"][0]
    assert form["status"] == "editing"
    payload = form["payload"]
    assert payload["product_code"] == MOCK_PRODUCT
    assert "一盘货仓" in payload["initial_ship_warehouse"]
    assert payload["transfer_qty"] == 1600
    assert form["context"]["from_site_code"] == MOCK_BASE_TIANJIN
