"""Mock case Script1 metric contract tests (requires YL PG with warehouse_sku_inventory)."""

import pytest

from app.yl_worker2.tools.metrics import (
    calc_replenishment_quantity_tool,
    eval_national_supply_status_tool,
    eval_target_stock_rate_tool,
    get_current_stock_rate,
    get_order_gap,
    get_order_progress,
    get_ship_gap,
)
from tests.yl_worker2.conftest import (
    MOCK_PRODUCT,
    MOCK_SITE_ZHENGZHOU,
    MOCK_SNAPSHOT_DATE,
    requires_yl_db,
)


@pytest.mark.asyncio
@requires_yl_db
async def test_script1_exception_a_order_gap(require_p1_snapshot):
    result = await get_order_gap(MOCK_PRODUCT, MOCK_SITE_ZHENGZHOU, MOCK_SNAPSHOT_DATE)
    assert "error" not in result
    # 现货 1606 + 在途 300 − 未发 4200
    assert result["order_gap"] == -2294


@pytest.mark.asyncio
@requires_yl_db
async def test_script1_exception_a_ship_gap(require_p1_snapshot):
    """现货 1606 − 未发 4200 = −2594（不含在途）。"""
    result = await get_ship_gap(MOCK_PRODUCT, MOCK_SITE_ZHENGZHOU, MOCK_SNAPSHOT_DATE)
    assert "error" not in result
    assert result["ship_gap"] == -2594
    assert result["store_num"] == 1606
    assert result["total_unship"] == 4200


@pytest.mark.asyncio
@requires_yl_db
async def test_script1_exception_a_stock_rate(require_p1_snapshot):
    result = await get_current_stock_rate(MOCK_PRODUCT, MOCK_SITE_ZHENGZHOU, MOCK_SNAPSHOT_DATE)
    assert result["stock_rate_pct"] == pytest.approx(49.1, abs=0.2)


@pytest.mark.asyncio
@requires_yl_db
async def test_script1_exception_a_order_progress(require_p1_snapshot):
    result = await get_order_progress(MOCK_PRODUCT, MOCK_SITE_ZHENGZHOU, MOCK_SNAPSHOT_DATE)
    assert result["order_progress_pct"] == pytest.approx(72.0, abs=0.5)


@pytest.mark.asyncio
@requires_yl_db
async def test_script1_national_deficit(require_p1_snapshot):
    result = await eval_national_supply_status_tool(MOCK_PRODUCT, MOCK_SNAPSHOT_DATE)
    assert result["status"] == "DEFICIT"


@pytest.mark.asyncio
@requires_yl_db
async def test_script1_target_stock_rate_deficit_mid_month(require_p1_snapshot):
    result = await eval_target_stock_rate_tool(
        MOCK_PRODUCT, MOCK_SITE_ZHENGZHOU, MOCK_SNAPSHOT_DATE, "mid_month"
    )
    assert result["target_rate_pct"] == 72.0
    assert result["applied_rule"] == "deficit.mid_month.meet_order_only"


@pytest.mark.asyncio
@requires_yl_db
async def test_script1_replenishment_qty(require_p1_snapshot):
    result = await calc_replenishment_quantity_tool(
        MOCK_PRODUCT, MOCK_SITE_ZHENGZHOU, MOCK_SNAPSHOT_DATE, "mid_month"
    )
    assert result["replenishment_qty"] == 2294
