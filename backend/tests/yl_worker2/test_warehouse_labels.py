"""Unit tests for fulfillment warehouse label mapping."""

from app.yl_worker2.fulfillment.warehouse_labels import to_logic_warehouse_label


def test_to_logic_warehouse_label_adds_suffix():
    assert to_logic_warehouse_label("天津基地仓") == "天津基地仓一盘货仓"
    assert to_logic_warehouse_label("郑州销售仓") == "郑州销售仓一盘货仓"


def test_to_logic_warehouse_label_idempotent():
    assert to_logic_warehouse_label("天津基地仓一盘货仓") == "天津基地仓一盘货仓"
