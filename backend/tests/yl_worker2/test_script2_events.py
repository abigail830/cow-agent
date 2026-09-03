"""Script2 integration: pending orders + base availability after events."""

import pytest

from app.yl_worker2.obda import queries as obda
from app.yl_worker2.tools.allocation import list_pending_allocation_orders
from tests.yl_worker2.conftest import (
    MOCK_BASE_TIANJIN,
    MOCK_PRODUCT,
    MOCK_SITE_ZHENGZHOU,
    MOCK_SNAPSHOT_DATE,
    requires_yl_db,
)


@pytest.mark.asyncio
@requires_yl_db
async def test_script2_base_availability_after_delay(require_p1_snapshot):
    rows = await obda.fetch_base_warehouse_availability(
        MOCK_PRODUCT, MOCK_SNAPSHOT_DATE, to_site_code=MOCK_SITE_ZHENGZHOU
    )
    tj = next(
        (w for w in rows if w.get("from_site_code") == MOCK_BASE_TIANJIN),
        None,
    )
    assert tj is not None
    assert float(tj.get("from_available") or 0) == 3200.0
    assert tj.get("lead_time_days") == 2


@pytest.mark.asyncio
@requires_yl_db
async def test_script2_lists_pending_orders(require_p1_snapshot):
    result = await list_pending_allocation_orders(MOCK_PRODUCT, MOCK_SNAPSHOT_DATE)
    assert result["total_pending"] >= 1
    assert len(result["forward_orders"]) + len(result["lateral_orders"]) >= 1
