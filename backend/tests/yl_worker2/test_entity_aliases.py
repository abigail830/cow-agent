"""Unit tests for entity alias matching."""

from app.yl_worker2.runtime.entity_aliases import clear_alias_cache, load_entity_aliases, match_aliases


def setup_function():
    clear_alias_cache()


def test_load_entity_aliases_has_mock_entries():
    aliases = load_entity_aliases()
    assert len(aliases) >= 5
    codes = {(a["entity_type"], a["entity_id"], a["alias"]) for a in aliases}
    assert ("ProductSKU", "MOCK_YLP001", "小袋装原味牛奶片") in codes
    assert ("Warehouse", "MOCK_WH_S04", "郑州") in codes


def test_match_alias_product_by_name():
    hits = match_aliases("小袋装原味牛奶片", "ProductSKU")
    assert len(hits) == 1
    assert hits[0]["entity_id"] == "MOCK_YLP001"
    assert hits[0]["match_method"] == "alias.exact"


def test_match_alias_warehouse_zhengzhou_sales_context():
    hits = match_aliases("郑州", "Warehouse", site_type="sales")
    assert len(hits) == 1
    assert hits[0]["entity_id"] == "MOCK_WH_S04"


def test_match_alias_warehouse_zhengzhou_no_context_still_hits():
    hits = match_aliases("郑州仓", "Warehouse")
    assert len(hits) == 1
    assert hits[0]["entity_id"] == "MOCK_WH_S04"
