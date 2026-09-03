"""Unit tests for ontology_sources / ontology_refs config."""

from app.yl_worker2.runtime.ontology_config import (
    get_table_column_aliases,
    resolve_ref_rule,
    resolve_table_column,
    suggest_dimensions,
    table_allowed,
)


def test_table_allowed_yl_prefix():
    assert table_allowed("yl_product")
    assert table_allowed("yl_transit_inventory")
    assert table_allowed("warehouse_sku_inventory")
    assert table_allowed("transport_cost")


def test_table_allowed_rejects_other():
    assert not table_allowed("users")
    assert not table_allowed("")
    assert not table_allowed("pg_catalog")


def test_sql_like_pattern_semantics():
    assert table_allowed("yl_product")
    assert table_allowed("ylx")  # yl + one char
    assert not table_allowed("xyl_product")


def test_suggest_dimensions_orders_known_keys():
    cols = ["id", "product_code", "site_code", "qty", "from_site_code"]
    dims = suggest_dimensions(cols)
    assert "product_code" in dims
    assert "site_code" in dims
    assert "from_site_code" in dims


def test_resolve_ref_rule_exact_column():
    rule = resolve_ref_rule("from_site_code")
    assert rule is not None
    assert rule["target_table"] == "yl_warehouse"
    assert rule["target_column"] == "site_code"
    assert rule.get("role") == "source_warehouse"


def test_resolve_ref_rule_product_code():
    rule = resolve_ref_rule("product_code")
    assert rule is not None
    assert rule["target_table"] == "yl_product"


def test_resolve_ref_rule_transport_cost_columns():
    for col in ("from_warehouse_code", "to_warehouse_code"):
        rule = resolve_ref_rule(col)
        assert rule is not None
        assert rule["target_table"] == "yl_warehouse"
        assert rule["target_column"] == "site_code"


def test_resolve_ref_rule_unknown():
    assert resolve_ref_rule("not_a_ref") is None


def test_column_aliases_sales_warehouse_report():
    allowed = {"from_site_code", "product_code", "adjust_date"}
    aliases = get_table_column_aliases("yl_sales_warehouse_inventory_report", allowed)
    assert aliases["site_code"] == "from_site_code"
    assert resolve_table_column(
        "yl_sales_warehouse_inventory_report",
        "site_code",
        allowed,
        column_aliases=aliases,
    ) == "from_site_code"


def test_column_aliases_warehouse_sku_inventory():
    allowed = {"sku_code", "warehouse_code", "snapshot_date"}
    aliases = get_table_column_aliases("warehouse_sku_inventory", allowed)
    assert aliases["product_code"] == "sku_code"
    assert aliases["site_code"] == "warehouse_code"
