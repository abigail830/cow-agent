"""Snapshot catalog discovery tool tests."""

import pytest

from app.yl_worker2.tools.discovery import query_snapshot_catalog
from tests.yl_worker2.conftest import MOCK_PRODUCT, MOCK_SNAPSHOT_DATE, requires_yl_db


@pytest.mark.asyncio
@requires_yl_db
async def test_snapshot_catalog_lists_demo_date(require_p1_snapshot):
    result = await query_snapshot_catalog(MOCK_PRODUCT)
    assert MOCK_SNAPSHOT_DATE in result["available_dates"]
    assert result["recommended_adjust_date"] == MOCK_SNAPSHOT_DATE
    assert len(result["warehouse_master"]) >= 9


@pytest.mark.asyncio
@requires_yl_db
async def test_snapshot_catalog_sites_for_date(require_p1_snapshot):
    result = await query_snapshot_catalog(MOCK_PRODUCT, MOCK_SNAPSHOT_DATE)
    sites = {s["site_code"] for s in result["sites_with_snapshot"]}
    assert "MOCK_WH_S04" in sites
