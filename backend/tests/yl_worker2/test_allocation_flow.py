"""Script1 allocation flow integration (draft → update → activate → mock UI)."""

import uuid

import pytest

from app.yl_worker2.tools.allocation import (
    activate_allocation_and_push,
    save_forward_allocation_draft,
    simulate_allocation_effect,
    update_allocation_quantity,
)
from tests.yl_worker2.conftest import (
    MOCK_BASE_TIANJIN,
    MOCK_PRODUCT,
    MOCK_SITE_ZHENGZHOU,
    MOCK_SNAPSHOT_DATE,
    requires_yl_db,
)

_TEST_REMARK = f"TEST-{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
@requires_yl_db
async def test_forward_draft_update_activate_dual_write(require_p1_snapshot):
    draft = await save_forward_allocation_draft(
        adjust_date=MOCK_SNAPSHOT_DATE,
        product_code=MOCK_PRODUCT,
        from_site_code=MOCK_BASE_TIANJIN,
        to_site_code=MOCK_SITE_ZHENGZHOU,
        trans_num=4700,
        reason="契约测试草案",
        remark=_TEST_REMARK,
        sync_mock_ui=True,
    )
    assert draft["status"] == "draft_saved"
    order_id = draft["order_id"]
    mock_no = draft["mock_transfer_order_no"]
    assert mock_no

    updated = await update_allocation_quantity(
        "forward",
        order_id,
        1600,
        mock_transfer_order_no=mock_no,
    )
    assert updated["trans_num"] == 1600

    activated = await activate_allocation_and_push(
        "forward",
        order_id,
        push_num=1600,
        mock_transfer_order_no=mock_no,
    )
    assert activated["status"] == "activated"
    assert activated["push_num"] == 1600

    from app.yl_worker2.db import yl_connect

    conn = await yl_connect()
    try:
        oip = await conn.fetchrow(
            "SELECT push_num, trans_num FROM yl_forward_transfer WHERE id = $1",
            order_id,
        )
        mock = await conn.fetchrow(
            "SELECT status, transfer_qty FROM mock_branch_replenishment_order WHERE transfer_order_no = $1",
            mock_no,
        )
        assert float(oip["push_num"]) == 1600
        assert mock["status"] == "生效"
        assert float(mock["transfer_qty"]) == 1600
    finally:
        await conn.close()


@pytest.mark.asyncio
@requires_yl_db
async def test_simulate_allocation_accepts_string_transfer_qty(require_p1_snapshot):
    result = await simulate_allocation_effect(
        MOCK_PRODUCT,
        MOCK_SITE_ZHENGZHOU,
        MOCK_SNAPSHOT_DATE,
        "2294",
    )
    assert "error" not in result
    assert result["transfer_qty"] == 2294
    assert result["stock_rate_after_pct"] == pytest.approx(72.0, abs=0.2)
