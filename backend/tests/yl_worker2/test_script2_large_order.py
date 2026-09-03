"""Script2 large-order event: 呼市订单进度变化."""

import pytest

from app.yl_worker2.tools.metrics import get_order_progress
from tests.yl_worker2.conftest import (
    MOCK_PRODUCT,
    MOCK_SITE_HUHEHAOTE,
    MOCK_SNAPSHOT_DATE,
    requires_yl_db,
)


@pytest.mark.asyncio
@requires_yl_db
async def test_script2_huhehaote_order_progress_after_large_order(require_p1_snapshot):
    """P2 脚本将呼市 order_completion_rate 调整为 114%（大订单 +2800）。"""
    result = await get_order_progress(
        MOCK_PRODUCT, MOCK_SITE_HUHEHAOTE, MOCK_SNAPSHOT_DATE
    )
    assert "error" not in result
    assert result["order_progress_pct"] == pytest.approx(114.0, abs=0.5)
