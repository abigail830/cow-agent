"""Unit tests for StandardPolicyMatrix / SupplyChainMetrics pure logic."""

from app.yl_worker2.runtime.policy_evaluator import (
    calc_order_gap,
    calc_replenishment_quantity,
    calc_ship_gap,
    eval_national_supply_status,
    eval_target_stock_rate,
)


def test_eval_national_supply_plentiful():
    result = eval_national_supply_status(186658, 82360)
    assert result["status"] == "PLENTIFUL"
    assert result["supply_demand_ratio"] > 1.05


def test_eval_target_stock_rate_script1_case():
    """Mock Script1 异常 A：充足态 + 中旬 + 订单进度 72% > 标准 50% → 目标 92%."""
    result = eval_target_stock_rate("PLENTIFUL", 0.72, "mid_month")
    assert result["target_rate"] == 0.92
    assert result["target_rate_pct"] == 92.0
    assert result["applied_rule"] == "plentiful.mid_month.order_above_standard"


def test_calc_replenishment_quantity_script1_case():
    """计划 10000，目标 92%，当前口径 4500 → 补货 4700."""
    result = calc_replenishment_quantity(10000, 0.92, 4500)
    assert result["replenishment_qty"] == 4700
    assert result["target_basis"] == 9200


def test_calc_order_gap_zhengzhou():
    """郑州：1200 + 300 - 4200 = -2700."""
    assert calc_order_gap(1200, 300, 4200) == -2700


def test_calc_ship_gap_zhengzhou():
    """郑州：1200 - 4200 = -3000（仅现货口径）。"""
    assert calc_ship_gap(1200, 4200) == -3000
