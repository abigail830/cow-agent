"""Batch big-date inventory query tests."""

import pytest

from app.yl_worker2.tools.inventory import query_batch_big_date_inventory
from tests.yl_worker2.conftest import (
    MOCK_PRODUCT,
    MOCK_SITE_TIANJIN_SALES,
    MOCK_SITE_ZHENGZHOU,
    requires_yl_db,
)


@pytest.mark.asyncio
@requires_yl_db
async def test_batch_big_date_guangzhou(require_p1_snapshot):
    result = await query_batch_big_date_inventory(MOCK_PRODUCT, "MOCK_WH_S03")
    assert result["batch_count"] >= 1
    assert result["total_big_date_num"] == 4200.0
    assert result["batches"][0].get("produce_date") == "2026-02-20"


@pytest.mark.asyncio
@requires_yl_db
async def test_batch_big_date_tianjin(require_p1_snapshot):
    result = await query_batch_big_date_inventory(
        MOCK_PRODUCT, MOCK_SITE_TIANJIN_SALES
    )
    assert result["total_big_date_num"] == 3200.0


@pytest.mark.asyncio
@requires_yl_db
async def test_batch_big_date_empty_site(require_p1_snapshot):
    result = await query_batch_big_date_inventory(
        MOCK_PRODUCT, MOCK_SITE_ZHENGZHOU
    )
    assert result["batch_count"] == 0
    assert result["total_big_date_num"] == 0
