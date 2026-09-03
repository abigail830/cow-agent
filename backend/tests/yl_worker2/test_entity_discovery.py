"""Integration tests for entity discovery / resolution tools."""

import pytest

from app.yl_worker2.tools.discovery import (
    list_products,
    list_warehouses,
    query_snapshot_catalog,
    resolve_entity,
    search_products,
    search_warehouses,
)
from tests.yl_worker2.conftest import (
    MOCK_PRODUCT,
    MOCK_SITE_ZHENGZHOU,
    MOCK_SNAPSHOT_DATE,
    requires_yl_db,
)


@pytest.mark.asyncio
@requires_yl_db
async def test_list_products_returns_catalog(require_p1_snapshot):
    result = await list_products(limit=20)
    assert result["count"] >= 1
    codes = {p["product_code"] for p in result["products"]}
    assert MOCK_PRODUCT in codes


@pytest.mark.asyncio
@requires_yl_db
async def test_list_warehouses_sales(require_p1_snapshot):
    result = await list_warehouses(site_type="sales", limit=20)
    assert result["count"] >= 9
    assert all(w.get("site_type_label") == "sales" for w in result["warehouses"])


@pytest.mark.asyncio
@requires_yl_db
async def test_list_products_keyword_milk(require_p1_snapshot):
    result = await list_products(keyword="牛奶片", limit=20)
    assert result["count"] >= 1
    assert any("牛奶片" in (p.get("product_name") or "") for p in result["products"])


@pytest.mark.asyncio
@requires_yl_db
async def test_list_warehouses_base_count(require_p1_snapshot):
    result = await list_warehouses(site_type="base", limit=20)
    assert result["count"] >= 4
    assert all(w.get("site_type_label") == "base" for w in result["warehouses"])


@pytest.mark.asyncio
@requires_yl_db
async def test_search_warehouse_zhengzhou(require_p1_snapshot):
    result = await search_warehouses("郑州仓", site_type="sales")
    assert result["count"] >= 1
    top = result["candidates"][0]
    assert top["site_code"] == MOCK_SITE_ZHENGZHOU


@pytest.mark.asyncio
@requires_yl_db
async def test_resolve_entity_product_by_code(require_p1_snapshot):
    result = await resolve_entity("ProductSKU", "MOCK_YLP001")
    assert result["status"] == "resolved"
    assert result["resolved_id"] == MOCK_PRODUCT


@pytest.mark.asyncio
@requires_yl_db
async def test_resolve_entity_warehouse_zhengzhou(require_p1_snapshot):
    result = await resolve_entity("Warehouse", "郑州", site_type="sales")
    assert result["status"] in ("resolved", "ambiguous")
    ids = [c["id"] for c in result["candidates"]]
    assert MOCK_SITE_ZHENGZHOU in ids
    if result["status"] == "resolved":
        assert result["resolved_id"] == MOCK_SITE_ZHENGZHOU


@pytest.mark.asyncio
@requires_yl_db
async def test_search_products_by_code_fragment(require_p1_snapshot):
    result = await search_products("YLP001")
    assert result["count"] >= 1
    assert any(c["product_code"] == MOCK_PRODUCT for c in result["candidates"])


@pytest.mark.asyncio
@requires_yl_db
async def test_snapshot_catalog_without_product_code(require_p1_snapshot):
    result = await query_snapshot_catalog()
    assert result.get("latest_adjust_date")
    assert len(result.get("products_with_snapshot") or []) >= 1
    assert len(result.get("warehouse_master") or []) >= 9


@pytest.mark.asyncio
@requires_yl_db
async def test_snapshot_catalog_by_date_only(require_p1_snapshot):
    result = await query_snapshot_catalog(adjust_date=MOCK_SNAPSHOT_DATE)
    assert result["recommended_adjust_date"] == MOCK_SNAPSHOT_DATE
    coverage = result.get("snapshot_coverage") or []
    assert len(coverage) >= 1
