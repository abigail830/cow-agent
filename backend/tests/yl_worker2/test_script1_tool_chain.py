"""Script1 metric + inventory read chain (no LLM, mirrors §10 mock case steps 1–5)."""

import pytest

from app.yl_worker2.tools.inventory import (
    query_base_warehouse_availability,
    query_inventory_snapshot,
)
from app.yl_worker2.tools.metrics import (
    calc_replenishment_quantity_tool,
    eval_national_supply_status_tool,
    eval_target_stock_rate_tool,
    get_order_gap,
)
from tests.yl_worker2.conftest import (
    MOCK_BASE_TIANJIN,
    MOCK_PRODUCT,
    MOCK_SITE_ZHENGZHOU,
    MOCK_SNAPSHOT_DATE,
    requires_yl_db,
)


@pytest.mark.asyncio
@requires_yl_db
async def test_script1_metrics_and_base_selection_chain(require_p1_snapshot):
    """巡检异常仓 → 全国状态 → 目标备货率 → 补货量 → 基地可发（含时效）。"""
    snap = await query_inventory_snapshot(
        MOCK_PRODUCT, MOCK_SITE_ZHENGZHOU, MOCK_SNAPSHOT_DATE
    )
    assert snap.get("found") is True
    assert snap.get("stock_rate_before_pct") == pytest.approx(45.0, abs=0.5)

    gap = await get_order_gap(MOCK_PRODUCT, MOCK_SITE_ZHENGZHOU, MOCK_SNAPSHOT_DATE)
    assert gap["order_gap"] == -2700

    national = await eval_national_supply_status_tool(MOCK_PRODUCT, MOCK_SNAPSHOT_DATE)
    assert national["status"] == "PLENTIFUL"

    target = await eval_target_stock_rate_tool(
        MOCK_PRODUCT, MOCK_SITE_ZHENGZHOU, MOCK_SNAPSHOT_DATE, "mid_month"
    )
    assert target["target_rate_pct"] == 92.0

    replen = await calc_replenishment_quantity_tool(
        MOCK_PRODUCT, MOCK_SITE_ZHENGZHOU, MOCK_SNAPSHOT_DATE, "mid_month"
    )
    assert replen["replenishment_qty"] == 4700

    bases = await query_base_warehouse_availability(
        MOCK_PRODUCT,
        MOCK_SNAPSHOT_DATE,
        to_site_code=MOCK_SITE_ZHENGZHOU,
    )
    warehouses = bases["warehouses"]
    assert len(warehouses) >= 1
    tj = next(
        (w for w in warehouses if w.get("from_site_code") == MOCK_BASE_TIANJIN),
        None,
    )
    assert tj is not None
    assert tj.get("from_available") is not None
    assert tj.get("lead_time_days") == 2
