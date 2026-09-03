"""Integration tests for ontology query tools (list/describe/query/follow_ref)."""

import pytest

from app.yl_worker2.tools.ontology_query import (
    describe_table,
    follow_ref,
    list_sources,
    query_source,
)
from tests.yl_worker2.conftest import (
    MOCK_PRODUCT,
    MOCK_SITE_ZHENGZHOU,
    requires_yl_db,
)


@pytest.mark.asyncio
@requires_yl_db
async def test_list_sources_returns_whitelist_tables():
    result = await list_sources()
    names = {s["table_name"] for s in result["sources"]}
    assert "yl_product" in names
    assert "yl_warehouse" in names
    assert result["count"] >= 5


@pytest.mark.asyncio
async def test_describe_table_rejects_non_whitelist():
    result = await describe_table("users")
    assert result["status"] == "not_allowed"


@pytest.mark.asyncio
@requires_yl_db
async def test_describe_table_yl_transit_inventory():
    result = await describe_table("yl_transit_inventory")
    assert result["status"] == "ok"
    col_names = {c["column_name"] for c in result["columns"]}
    assert "from_site_code" in col_names
    assert "to_site_code" in col_names
    assert "from_site_code" in result["ref_candidates"]


@pytest.mark.asyncio
@requires_yl_db
async def test_query_source_base_warehouses():
    result = await query_source(
        "yl_warehouse",
        where={"eq": {"site_type": 0}},
        select=["site_code", "site_name", "site_type"],
        limit=50,
    )
    assert result["status"] == "ok"
    assert result["count"] >= 4
    assert all(r["site_type"] == 0 for r in result["rows"])


@pytest.mark.asyncio
@requires_yl_db
async def test_query_source_product_contains_milk(require_p1_snapshot):
    result = await query_source(
        "yl_product",
        where={"contains": {"product_name": "牛奶片"}},
        select=["product_code", "product_name"],
        limit=20,
    )
    assert result["status"] == "ok"
    assert result["count"] >= 1
    codes = {r["product_code"] for r in result["rows"]}
    assert MOCK_PRODUCT in codes


@pytest.mark.asyncio
@requires_yl_db
async def test_follow_ref_from_site_code(require_p1_snapshot):
    transit = await query_source(
        "yl_transit_inventory",
        where={
            "and": [
                {"eq": {"product_code": MOCK_PRODUCT}},
                {"eq": {"to_site_code": MOCK_SITE_ZHENGZHOU}},
            ]
        },
        limit=5,
    )
    assert transit["status"] == "ok"
    if not transit["rows"]:
        pytest.skip("no transit rows for mock product → zhengzhou")
    row = transit["rows"][0]
    ref = await follow_ref("yl_transit_inventory", row, "from_site_code")
    assert ref["status"] in ("resolved", "ambiguous")
    assert ref["target_table"] == "yl_warehouse"
    assert ref["count"] >= 1
    assert "site_name" in ref["rows"][0]
