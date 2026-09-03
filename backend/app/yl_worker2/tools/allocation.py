"""AllocationOrder ontology tools — OIP + mock_branch_replenishment_order dual-write."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from agent_framework import tool

from app.yl_worker2.allocation_links import (
    embed_mock_no,
    extract_mock_no,
    is_cancelled_remark,
    mark_cancelled_remark,
)
from app.yl_worker2.db import parse_adjust_date, yl_connect
from app.yl_worker2.obda import queries as obda
from app.yl_worker2.runtime.parse import parse_qty

_ALLOC_TYPE = Literal["forward", "lateral"]


def _transfer_order_no(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:24].upper()}"


async def _sync_mock_replenishment(
    conn,
    *,
    transfer_order_no: str,
    product_code: str,
    product_name: str,
    business: str,
    from_site_name: str,
    to_site_name: str,
    transfer_qty: float,
    status: str,
    remark: str | None = None,
) -> str:
    await conn.execute(
        """
        INSERT INTO mock_branch_replenishment_order (
            transfer_order_no, product_code, sku_code, product_name, unit, business_unit,
            status, transfer_gen_status, transfer_qty,
            initial_ship_warehouse, outbound_logic_warehouse, inbound_logic_warehouse,
            shipping_remark, created_at, updated_at
        ) VALUES (
            $1, $2, $2, $3, 'EA', $4,
            $5, '未生成', $6,
            $7, $7, $8,
            $9, now(), now()
        )
        ON CONFLICT (transfer_order_no) DO UPDATE SET
            transfer_qty = EXCLUDED.transfer_qty,
            status = EXCLUDED.status,
            shipping_remark = EXCLUDED.shipping_remark,
            updated_at = now()
        """,
        transfer_order_no,
        product_code,
        product_name,
        business,
        status,
        transfer_qty,
        from_site_name,
        to_site_name,
        remark,
    )
    return transfer_order_no


async def _resolve_mock_no(conn, table: str, order_id: int, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    row = await conn.fetchrow(f"SELECT remark FROM {table} WHERE id = $1", order_id)
    if row is None:
        return None
    return extract_mock_no(row["remark"])


@tool(
    name="list_pending_allocation_orders",
    description=(
        "【AllocationOrder 草案】列出待经理确认的调拨行（push_num IS NULL）。\n"
        "业务含义：外系统事件或巡检后，查看尚未下发的正向/横向建议。\n"
        "规则：仅返回未作废、未下发的 OIP 行；remark 含 |MOCK_NO:...| 可与履约表关联。\n"
        "何时调用：Script2 事件后检查草案可行性；经理确认前盘点待办。\n"
        "输入：product_code, adjust_date（可选 YYYY-MM-DD）。\n"
        "返回：forward_orders, lateral_orders, total_pending。"
    ),
)
async def list_pending_allocation_orders(
    product_code: str,
    adjust_date: str | None = None,
) -> dict:
    forward = await obda.fetch_pending_forward_orders(product_code, adjust_date)
    lateral = await obda.fetch_pending_lateral_orders(product_code, adjust_date)
    return {
        "product_code": product_code,
        "adjust_date": adjust_date,
        "forward_orders": forward,
        "lateral_orders": lateral,
        "total_pending": len(forward) + len(lateral),
    }


@tool(
    name="simulate_allocation_effect",
    description=(
        "【仿真】给定调入量，估算收货仓调拨后生产备货率。\n"
        "公式：调后备货率 = (现货+在途+累出+调入量) / 销售计划。\n"
        "何时调用：经理解读方案前，对比调前/调后备货率。\n"
        "输入：product_code, to_site_code, adjust_date, transfer_qty。\n"
        "返回：stock_rate_before/after（含 pct）, applied_rule。"
    ),
)
async def simulate_allocation_effect(
    product_code: str,
    to_site_code: str,
    adjust_date: str,
    transfer_qty: float,
) -> dict:
    snap = await obda.fetch_inventory_snapshot(product_code, to_site_code, adjust_date)
    if snap is None:
        return {"error": "inventory_snapshot_not_found"}
    qty = parse_qty(transfer_qty)
    plan = parse_qty(snap.get("plan_num"))
    store = parse_qty(snap.get("store_num"))
    transit = parse_qty(snap.get("store_transit"))
    output = parse_qty(snap.get("out_put_num"))
    before = (store + transit + output) / plan if plan else 0.0
    after = (store + transit + output + qty) / plan if plan else 0.0
    return {
        "product_code": product_code,
        "to_site_code": to_site_code,
        "adjust_date": adjust_date,
        "transfer_qty": qty,
        "stock_rate_before": round(before, 4),
        "stock_rate_after": round(after, 4),
        "stock_rate_before_pct": round(before * 100, 1),
        "stock_rate_after_pct": round(after * 100, 1),
        "applied_rule": "simulation.add_transfer_to_stock_basis",
    }


@tool(
    name="save_forward_allocation_draft",
    description=(
        "【AllocationOrder.save_as_draft 正向】写入 yl_forward_transfer 草案（push_num=NULL）。\n"
        "业务含义：基地仓→销售仓正向补货建议，默认同步履约表 status=草稿。\n"
        "规则：remark 写入 |MOCK_NO:xxx| 供后续改量/下发自动关联履约行。\n"
        "何时调用：Script1 算出补货量后写正向草案。\n"
        "输入：adjust_date, product_code, from_site_code, to_site_code, trans_num, reason, remark。\n"
        "返回：order_id, mock_transfer_order_no, trans_num, status=draft_saved。"
    ),
)
async def save_forward_allocation_draft(
    adjust_date: str,
    product_code: str,
    from_site_code: str,
    to_site_code: str,
    trans_num: float,
    reason: str,
    remark: str = "",
    sync_mock_ui: bool = True,
) -> dict:
    conn = await yl_connect()
    try:
        async with conn.transaction():
            to_snap = await obda.fetch_inventory_snapshot(product_code, to_site_code, adjust_date)
            from_row = await conn.fetchrow(
                "SELECT site_name FROM yl_warehouse WHERE site_code = $1 LIMIT 1",
                from_site_code,
            )
            to_row = await conn.fetchrow(
                "SELECT site_name FROM yl_warehouse WHERE site_code = $1 LIMIT 1",
                to_site_code,
            )
            prod = await conn.fetchrow(
                "SELECT product_name, business, business_code FROM yl_product WHERE product_code = $1 LIMIT 1",
                product_code,
            )
            mock_no = _transfer_order_no("BR-OIP-FWD") if sync_mock_ui else None
            final_remark = embed_mock_no(remark, mock_no) if mock_no else remark
            row_id = await conn.fetchval(
                """
                INSERT INTO yl_forward_transfer (
                    adjust_date, business, business_code, product_code, product_name,
                    from_site_code, from_site_name, to_site_code, to_site_name,
                    trans_num_jh, trans_num, reason, remark, push_user,
                    to_plan_num, to_store_num, to_store_transit, to_out_put_num,
                    to_available_quantity, to_order_completion_rate, to_stock_rate_before
                ) VALUES (
                    $1::date, $2, $3, $4, $5,
                    $6, $7, $8, $9,
                    $10, $10, $11, $12, 'AGENTOS',
                    $13, $14, $15, $16, $17, $18, $19
                )
                RETURNING id
                """,
                parse_adjust_date(adjust_date),
                prod["business"] if prod else "成人营养品事业部",
                prod["business_code"] if prod else "CRYYBU",
                product_code,
                prod["product_name"] if prod else product_code,
                from_site_code,
                from_row["site_name"] if from_row else from_site_code,
                to_site_code,
                to_row["site_name"] if to_row else to_site_code,
                trans_num,
                reason,
                final_remark,
                to_snap.get("plan_num") if to_snap else None,
                to_snap.get("store_num") if to_snap else None,
                to_snap.get("store_transit") if to_snap else None,
                to_snap.get("out_put_num") if to_snap else None,
                to_snap.get("total_unship") if to_snap else None,
                to_snap.get("order_completion_rate") if to_snap else None,
                to_snap.get("stock_rate_before") if to_snap else None,
            )
            if sync_mock_ui and mock_no:
                await _sync_mock_replenishment(
                    conn,
                    transfer_order_no=mock_no,
                    product_code=product_code,
                    product_name=prod["product_name"] if prod else product_code,
                    business=prod["business"] if prod else "成人营养品事业部",
                    from_site_name=from_row["site_name"] if from_row else from_site_code,
                    to_site_name=to_row["site_name"] if to_row else to_site_code,
                    transfer_qty=trans_num,
                    status="草稿",
                    remark=remark or reason,
                )
        return {
            "status": "draft_saved",
            "allocation_type": "forward",
            "order_id": row_id,
            "mock_transfer_order_no": mock_no,
            "trans_num": trans_num,
        }
    finally:
        await conn.close()


@tool(
    name="save_lateral_allocation_draft",
    description=(
        "【AllocationOrder.save_as_draft 横向】写入 yl_lateral_transfer 草案（push_num=NULL）。\n"
        "业务含义：销售仓→销售仓横调，常用于大日期消化。\n"
        "规则：同步写履约表草稿；remark 含 |MOCK_NO:xxx| 自动关联。\n"
        "何时调用：异常 B 大日期调出、就近横调方案。\n"
        "输入：adjust_date, product_code, from_site_code, to_site_code, trans_num, reason, remark。\n"
        "返回：order_id, mock_transfer_order_no, trans_num。"
    ),
)
async def save_lateral_allocation_draft(
    adjust_date: str,
    product_code: str,
    from_site_code: str,
    to_site_code: str,
    trans_num: float,
    reason: str,
    remark: str = "",
    sync_mock_ui: bool = True,
) -> dict:
    conn = await yl_connect()
    try:
        async with conn.transaction():
            from_row = await conn.fetchrow(
                "SELECT site_name FROM yl_warehouse WHERE site_code = $1 LIMIT 1",
                from_site_code,
            )
            to_row = await conn.fetchrow(
                "SELECT site_name FROM yl_warehouse WHERE site_code = $1 LIMIT 1",
                to_site_code,
            )
            prod = await conn.fetchrow(
                "SELECT product_name, business, business_code FROM yl_product WHERE product_code = $1 LIMIT 1",
                product_code,
            )
            mock_no = _transfer_order_no("BR-OIP-LAT") if sync_mock_ui else None
            final_remark = embed_mock_no(remark, mock_no) if mock_no else remark
            row_id = await conn.fetchval(
                """
                INSERT INTO yl_lateral_transfer (
                    adjust_date, business, business_code, product_code, product_name,
                    from_site_code, from_site_name, to_site_code, to_site_name,
                    trans_num_jh, trans_num, reason, remark, push_user
                ) VALUES (
                    $1::date, $2, $3, $4, $5,
                    $6, $7, $8, $9,
                    $10, $10, $11, $12, 'AGENTOS'
                )
                RETURNING id
                """,
                parse_adjust_date(adjust_date),
                prod["business"] if prod else "成人营养品事业部",
                prod["business_code"] if prod else "CRYYBU",
                product_code,
                prod["product_name"] if prod else product_code,
                from_site_code,
                from_row["site_name"] if from_row else from_site_code,
                to_site_code,
                to_row["site_name"] if to_row else to_site_code,
                trans_num,
                reason,
                final_remark,
            )
            if sync_mock_ui and mock_no:
                await _sync_mock_replenishment(
                    conn,
                    transfer_order_no=mock_no,
                    product_code=product_code,
                    product_name=prod["product_name"] if prod else product_code,
                    business=prod["business"] if prod else "成人营养品事业部",
                    from_site_name=from_row["site_name"] if from_row else from_site_code,
                    to_site_name=to_row["site_name"] if to_row else to_site_code,
                    transfer_qty=trans_num,
                    status="草稿",
                    remark=remark or reason,
                )
        return {
            "status": "draft_saved",
            "allocation_type": "lateral",
            "order_id": row_id,
            "mock_transfer_order_no": mock_no,
            "trans_num": trans_num,
        }
    finally:
        await conn.close()


@tool(
    name="update_allocation_quantity",
    description=(
        "【经理改量】更新 OIP trans_num 并同步 mock_branch_replenishment_order.transfer_qty。\n"
        "规则：若未传 mock_transfer_order_no，从 OIP remark 的 |MOCK_NO:...| 自动解析。\n"
        "何时调用：经理将建议量改为确认量（如 4700→1600）。\n"
        "输入：allocation_type（forward|lateral）, order_id, trans_num, mock_transfer_order_no（可选）。\n"
        "返回：status=updated, trans_num, mock_transfer_order_no。"
    ),
)
async def update_allocation_quantity(
    allocation_type: _ALLOC_TYPE,
    order_id: int,
    trans_num: float,
    mock_transfer_order_no: str | None = None,
) -> dict:
    table = "yl_forward_transfer" if allocation_type == "forward" else "yl_lateral_transfer"
    conn = await yl_connect()
    try:
        async with conn.transaction():
            mock_no = await _resolve_mock_no(conn, table, order_id, mock_transfer_order_no)
            updated = await conn.fetchrow(
                f"""
                UPDATE {table}
                SET trans_num = $2, reason = COALESCE(reason, '') || ' [经理改量]'
                WHERE id = $1
                RETURNING id, product_code, trans_num, remark
                """,
                order_id,
                trans_num,
            )
            if updated is None:
                return {"error": "order_not_found", "order_id": order_id}
            if mock_no is None:
                mock_no = extract_mock_no(updated["remark"])
            if mock_no:
                await conn.execute(
                    """
                    UPDATE mock_branch_replenishment_order
                    SET transfer_qty = $2, updated_at = now()
                    WHERE transfer_order_no = $1
                    """,
                    mock_no,
                    trans_num,
                )
        return {
            "status": "updated",
            "allocation_type": allocation_type,
            "order_id": order_id,
            "trans_num": trans_num,
            "mock_transfer_order_no": mock_no,
        }
    finally:
        await conn.close()


@tool(
    name="activate_allocation_and_push",
    description=(
        "【AllocationOrder.activate_and_push】经理确认下发。\n"
        "规则：UPDATE OIP push_num/push_time/push_user；履约表 status=生效。\n"
        "自动从 remark |MOCK_NO:...| 关联履约行，避免重复 INSERT。\n"
        "何时调用：经理明确确认后。\n"
        "输入：allocation_type, order_id, push_num（默认=trans_num）, mock_transfer_order_no（可选）。\n"
        "返回：status=activated, push_num, push_time, mock_transfer_order_no。"
    ),
)
async def activate_allocation_and_push(
    allocation_type: _ALLOC_TYPE,
    order_id: int,
    push_num: float | None = None,
    push_user: str = "MANAGER",
    mock_transfer_order_no: str | None = None,
) -> dict:
    table = "yl_forward_transfer" if allocation_type == "forward" else "yl_lateral_transfer"
    conn = await yl_connect()
    try:
        async with conn.transaction():
            row = await conn.fetchrow(f"SELECT * FROM {table} WHERE id = $1", order_id)
            if row is None:
                return {"error": "order_not_found", "order_id": order_id}
            qty = push_num if push_num is not None else float(row["trans_num"])
            now = datetime.now()
            await conn.execute(
                f"""
                UPDATE {table}
                SET push_num = $2, push_time = $3, push_user = $4
                WHERE id = $1
                """,
                order_id,
                qty,
                now,
                push_user,
            )
            mock_no = await _resolve_mock_no(conn, table, order_id, mock_transfer_order_no)
            if mock_no is None:
                mock_no = extract_mock_no(row["remark"])
            if mock_no:
                await conn.execute(
                    """
                    UPDATE mock_branch_replenishment_order
                    SET status = '生效', transfer_qty = $2, updated_at = now()
                    WHERE transfer_order_no = $1
                    """,
                    mock_no,
                    qty,
                )
            else:
                mock_no = await _sync_mock_replenishment(
                    conn,
                    transfer_order_no=_transfer_order_no("BR-OIP-ACT"),
                    product_code=row["product_code"],
                    product_name=row["product_name"],
                    business=row["business"],
                    from_site_name=row["from_site_name"],
                    to_site_name=row["to_site_name"],
                    transfer_qty=qty,
                    status="生效",
                    remark=row["remark"] if row["remark"] else None,
                )
        return {
            "status": "activated",
            "allocation_type": allocation_type,
            "order_id": order_id,
            "push_num": qty,
            "push_time": now.isoformat(),
            "mock_transfer_order_no": mock_no,
        }
    finally:
        await conn.close()


@tool(
    name="cancel_allocation_order",
    description=(
        "【AllocationOrder.cancel_order】作废调拨行。\n"
        "规则：横向 is_delete=1；正向 remark 标记 [已作废]；履约表 status=作废。\n"
        "自动从 remark |MOCK_NO:...| 同步履约作废。\n"
        "何时调用：经理驳回或事件导致方案不可行。\n"
        "输入：allocation_type, order_id, mock_transfer_order_no（可选）。\n"
        "返回：status=cancelled。"
    ),
)
async def cancel_allocation_order(
    allocation_type: _ALLOC_TYPE,
    order_id: int,
    mock_transfer_order_no: str | None = None,
) -> dict:
    table = "yl_forward_transfer" if allocation_type == "forward" else "yl_lateral_transfer"
    conn = await yl_connect()
    try:
        async with conn.transaction():
            row = await conn.fetchrow(f"SELECT remark FROM {table} WHERE id = $1", order_id)
            if row is None:
                return {"error": "order_not_found", "order_id": order_id}
            mock_no = await _resolve_mock_no(conn, table, order_id, mock_transfer_order_no)
            if mock_no is None:
                mock_no = extract_mock_no(row["remark"])

            if allocation_type == "lateral":
                updated = await conn.fetchval(
                    f"UPDATE {table} SET is_delete = 1 WHERE id = $1 RETURNING id",
                    order_id,
                )
            else:
                if is_cancelled_remark(row["remark"]):
                    updated = order_id
                else:
                    updated = await conn.fetchval(
                        f"""
                        UPDATE {table}
                        SET remark = $2
                        WHERE id = $1
                        RETURNING id
                        """,
                        order_id,
                        mark_cancelled_remark(row["remark"]),
                    )
            if updated is None:
                return {"error": "order_not_found", "order_id": order_id}
            if mock_no:
                await conn.execute(
                    """
                    UPDATE mock_branch_replenishment_order
                    SET status = '作废', updated_at = now()
                    WHERE transfer_order_no = $1
                    """,
                    mock_no,
                )
        return {
            "status": "cancelled",
            "allocation_type": allocation_type,
            "order_id": order_id,
            "mock_transfer_order_no": mock_no,
        }
    finally:
        await conn.close()
