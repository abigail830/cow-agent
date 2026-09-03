"""Inventory snapshot includes big_date from VIEW."""

import pytest

from app.yl_worker2.tools.inventory import query_inventory_snapshot
from tests.yl_worker2.conftest import (
    MOCK_PRODUCT,
    MOCK_SITE_TIANJIN_SALES,
    MOCK_SNAPSHOT_DATE,
    requires_yl_db,
)


@pytest.mark.asyncio
@requires_yl_db
async def test_tianjin_snapshot_includes_big_date(require_p1_snapshot):
    snap = await query_inventory_snapshot(
        MOCK_PRODUCT, MOCK_SITE_TIANJIN_SALES, MOCK_SNAPSHOT_DATE
    )
    assert snap["found"] is True
    assert float(snap.get("big_date_num") or 0) == 3200.0
