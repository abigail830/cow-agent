"""Extended allocation flow: lateral, cancel, auto mock_no lookup."""

import uuid

import pytest

from app.yl_worker2.allocation_links import extract_mock_no
from app.yl_worker2.db import yl_connect
from app.yl_worker2.tools.allocation import (
    activate_allocation_and_push,
    cancel_allocation_order,
    save_forward_allocation_draft,
    save_lateral_allocation_draft,
    update_allocation_quantity,
)
from tests.yl_worker2.conftest import (
    MOCK_BASE_TIANJIN,
    MOCK_PRODUCT,
    MOCK_SITE_HUHEHAOTE,
    MOCK_SITE_TIANJIN_SALES,
    MOCK_SITE_ZHENGZHOU,
    MOCK_SNAPSHOT_DATE,
    requires_yl_db,
)

_TEST_REMARK = lambda: f"TEST-{uuid.uuid4().hex[:8]}"


@pytest.mark.asyncio
@requires_yl_db
async def test_update_without_explicit_mock_no(require_p1_snapshot):
    """remark 中的 |MOCK_NO:...| 应能自动同步履约改量。"""
    remark = _TEST_REMARK()
    draft = await save_forward_allocation_draft(
        adjust_date=MOCK_SNAPSHOT_DATE,
        product_code=MOCK_PRODUCT,
        from_site_code=MOCK_BASE_TIANJIN,
        to_site_code=MOCK_SITE_ZHENGZHOU,
        trans_num=2000,
        reason="自动关联测试",
        remark=remark,
    )
    order_id = draft["order_id"]
    mock_no = draft["mock_transfer_order_no"]

    updated = await update_allocation_quantity("forward", order_id, 1800)
    assert updated["mock_transfer_order_no"] == mock_no
    assert updated["trans_num"] == 1800

    conn = await yl_connect()
    try:
        mock = await conn.fetchrow(
            "SELECT transfer_qty FROM mock_branch_replenishment_order WHERE transfer_order_no = $1",
            mock_no,
        )
        oip = await conn.fetchrow(
            "SELECT remark FROM yl_forward_transfer WHERE id = $1",
            order_id,
        )
        assert float(mock["transfer_qty"]) == 1800
        assert extract_mock_no(oip["remark"]) == mock_no
    finally:
        await conn.close()


@pytest.mark.asyncio
@requires_yl_db
async def test_lateral_draft_and_cancel_dual_write(require_p1_snapshot):
    remark = _TEST_REMARK()
    draft = await save_lateral_allocation_draft(
        adjust_date=MOCK_SNAPSHOT_DATE,
        product_code=MOCK_PRODUCT,
        from_site_code=MOCK_SITE_TIANJIN_SALES,
        to_site_code=MOCK_SITE_HUHEHAOTE,
        trans_num=2500,
        reason="横调契约测试",
        remark=remark,
    )
    order_id = draft["order_id"]
    mock_no = draft["mock_transfer_order_no"]

    cancelled = await cancel_allocation_order("lateral", order_id)
    assert cancelled["status"] == "cancelled"
    assert cancelled["mock_transfer_order_no"] == mock_no

    conn = await yl_connect()
    try:
        oip = await conn.fetchrow(
            "SELECT is_delete FROM yl_lateral_transfer WHERE id = $1",
            order_id,
        )
        mock = await conn.fetchrow(
            "SELECT status FROM mock_branch_replenishment_order WHERE transfer_order_no = $1",
            mock_no,
        )
        assert int(oip["is_delete"]) == 1
        assert mock["status"] == "作废"
    finally:
        await conn.close()


@pytest.mark.asyncio
@requires_yl_db
async def test_forward_cancel_dual_write(require_p1_snapshot):
    remark = _TEST_REMARK()
    draft = await save_forward_allocation_draft(
        adjust_date=MOCK_SNAPSHOT_DATE,
        product_code=MOCK_PRODUCT,
        from_site_code=MOCK_BASE_TIANJIN,
        to_site_code=MOCK_SITE_ZHENGZHOU,
        trans_num=500,
        reason="作废测试",
        remark=remark,
    )
    order_id = draft["order_id"]
    mock_no = draft["mock_transfer_order_no"]

    cancelled = await cancel_allocation_order("forward", order_id)
    assert cancelled["status"] == "cancelled"

    conn = await yl_connect()
    try:
        oip = await conn.fetchrow(
            "SELECT remark FROM yl_forward_transfer WHERE id = $1",
            order_id,
        )
        mock = await conn.fetchrow(
            "SELECT status FROM mock_branch_replenishment_order WHERE transfer_order_no = $1",
            mock_no,
        )
        assert "[已作废]" in oip["remark"]
        assert mock["status"] == "作废"
    finally:
        await conn.close()


@pytest.mark.asyncio
@requires_yl_db
async def test_activate_reuses_mock_row_not_duplicate(require_p1_snapshot):
    remark = _TEST_REMARK()
    draft = await save_forward_allocation_draft(
        adjust_date=MOCK_SNAPSHOT_DATE,
        product_code=MOCK_PRODUCT,
        from_site_code=MOCK_BASE_TIANJIN,
        to_site_code=MOCK_SITE_ZHENGZHOU,
        trans_num=900,
        reason="下发复用测试",
        remark=remark,
    )
    order_id = draft["order_id"]
    mock_no = draft["mock_transfer_order_no"]

    activated = await activate_allocation_and_push("forward", order_id, push_num=900)
    assert activated["mock_transfer_order_no"] == mock_no

    conn = await yl_connect()
    try:
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM mock_branch_replenishment_order WHERE transfer_order_no = $1",
            mock_no,
        )
        status = await conn.fetchval(
            "SELECT status FROM mock_branch_replenishment_order WHERE transfer_order_no = $1",
            mock_no,
        )
        assert count == 1
        assert status == "生效"
    finally:
        await conn.close()
