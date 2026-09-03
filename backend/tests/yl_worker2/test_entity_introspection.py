"""Tests for L0 entity introspection tools and alias-backed resolution."""

import pytest

from app.yl_worker2.tools.discovery import resolve_entity, search_products
from app.yl_worker2.tools.introspection import describe_entity_type, list_entity_types
from tests.yl_worker2.conftest import (
    MOCK_PRODUCT,
    MOCK_SITE_ZHENGZHOU,
    requires_yl_db,
)


@pytest.mark.asyncio
async def test_list_entity_types():
    result = await list_entity_types()
    names = {t["name"] for t in result["entity_types"]}
    assert "ProductSKU" in names
    assert "Warehouse" in names
    assert "InventorySnapshot" in names
    assert result["count"] >= 4


@pytest.mark.asyncio
async def test_describe_entity_type_product():
    result = await describe_entity_type("ProductSKU")
    assert result["status"] == "ok"
    assert result["id_field"] == "product_code"
    assert "list_products" in result["discovery_tools"]
    assert "resolve_entity" in result["resolution_tools"]


@pytest.mark.asyncio
async def test_describe_entity_type_alias_warehouse():
    result = await describe_entity_type("warehouse")
    assert result["status"] == "ok"
    assert result["entity_type"] == "Warehouse"


@pytest.mark.asyncio
async def test_describe_entity_type_unknown():
    result = await describe_entity_type("NotARealType")
    assert result["status"] == "not_found"
    assert "ProductSKU" in result["supported_types"]


@pytest.mark.asyncio
@requires_yl_db
async def test_resolve_entity_product_via_alias(require_p1_snapshot):
    result = await resolve_entity("ProductSKU", "小袋装原味牛奶片")
    assert result["status"] == "resolved"
    assert result["resolved_id"] == MOCK_PRODUCT
    assert result["candidates"][0]["match_method"] == "alias.exact"


@pytest.mark.asyncio
@requires_yl_db
async def test_search_products_via_alias(require_p1_snapshot):
    result = await search_products("小袋装原味牛奶片")
    assert result["count"] >= 1
    assert result["candidates"][0]["product_code"] == MOCK_PRODUCT
    assert result["candidates"][0]["match_method"] == "alias.exact"


@pytest.mark.asyncio
@requires_yl_db
async def test_resolve_entity_warehouse_via_alias(require_p1_snapshot):
    result = await resolve_entity("Warehouse", "郑州", site_type="sales")
    assert result["status"] == "resolved"
    assert result["resolved_id"] == MOCK_SITE_ZHENGZHOU
