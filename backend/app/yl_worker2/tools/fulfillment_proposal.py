"""Propose fulfillment branch-replenishment forms (session-only until user Confirm)."""

from __future__ import annotations

from typing import Any, Literal

from agent_framework import tool

from app.yl_worker2.fulfillment.context import get_run_fulfillment_forms_state
from app.yl_worker2.fulfillment.forms import build_fulfillment_form
from app.yl_worker2.fulfillment.schemas import (
    FulfillmentProposalResult,
    ProposeFulfillmentInput,
)
from app.yl_worker2.tools.allocation import simulate_allocation_effect

_ALLOC_TYPE = Literal["forward", "lateral"]


@tool(
    schema=ProposeFulfillmentInput,
    name="propose_fulfillment_forms",
    description=(
        "【履约补录单提案】根据补调方案生成一张或多张分仓补录单表单（会话暂存，不写 OIP）。\n"
        "表单字段对齐履约中心 POST /fulfillment/branch-replenishment：\n"
        "必填 payload：product_code, business_unit（成人营养品事业部，与 yl_product.business / 履约中心一致）, "
        "initial/outbound/inbound_logic_warehouse（逻辑仓展示名）, "
        "transfer_qty, planned_ship_at, expected_arrival_at。\n"
        "可选：sku_code, merchant_order_no, source_order_no, transit_warehouse, shipping_remark, temp_zone。\n"
        "context 保留 from_site_code/to_site_code 供推理；仓名由 site_code 映射为一盘货仓展示名。\n"
        "何时调用：完成指标链与 simulate 后，向经理提交可审阅的补录单草案；禁止直接 save_*_draft / activate_*。\n"
        "输入：product_code, adjust_date, business_unit（建议传成人营养品事业部；不确定时先 search_products 取 business）, "
        "lines[]（每条含 allocation_type, from_site_code, to_site_code, "
        "transfer_qty, reason；可选 simulation/shipping_remark/时间字段）。\n"
        "返回：forms[]（含 form_id, payload, context, fingerprint）, count；前端据此渲染表单。"
    ),
)
async def propose_fulfillment_forms(
    product_code: str,
    adjust_date: str,
    lines: list[dict[str, Any]],
    business_unit: str | None = None,
    source_order_no: str | None = None,
    summary: str = "",
) -> dict:
    if not lines:
        return FulfillmentProposalResult(status="error", error="lines must not be empty").model_dump()

    built: list[dict[str, Any]] = []
    for idx, line in enumerate(lines):
        alloc_type = str(line.get("allocation_type") or "forward").strip().lower()
        if alloc_type not in ("forward", "lateral"):
            return FulfillmentProposalResult(
                status="error", error=f"lines[{idx}].allocation_type invalid"
            ).model_dump()
        from_code = str(line.get("from_site_code") or "").strip()
        to_code = str(line.get("to_site_code") or "").strip()
        qty = float(line.get("transfer_qty") or 0)
        reason = str(line.get("reason") or summary or "补调建议")
        if not from_code or not to_code:
            return FulfillmentProposalResult(
                status="error", error=f"lines[{idx}] missing site codes"
            ).model_dump()

        simulation = line.get("simulation")
        if simulation is None and alloc_type == "forward":
            simulation = await simulate_allocation_effect(
                product_code, to_code, adjust_date, qty
            )
            if simulation.get("error"):
                simulation = None

        try:
            form = await build_fulfillment_form(
                product_code=product_code,
                adjust_date=adjust_date,
                allocation_type=alloc_type,  # type: ignore[arg-type]
                from_site_code=from_code,
                to_site_code=to_code,
                transfer_qty=qty,
                reason=reason,
                business_unit=business_unit,
                source_order_no=line.get("source_order_no") or source_order_no,
                shipping_remark=line.get("shipping_remark"),
                planned_ship_at=line.get("planned_ship_at"),
                expected_arrival_at=line.get("expected_arrival_at"),
                transit_warehouse=str(line.get("transit_warehouse") or "-"),
                temp_zone=str(line.get("temp_zone") or "常温"),
                merchant_order_no=line.get("merchant_order_no"),
                simulation=simulation if isinstance(simulation, dict) else None,
                summary=summary,
            )
        except ValueError as exc:
            return FulfillmentProposalResult(status="error", error=str(exc)).model_dump()
        built.append(form)

    ctx = get_run_fulfillment_forms_state()
    if ctx is not None:
        ctx.forms = built
        ctx.mark_dirty()

    return FulfillmentProposalResult(
        status="proposed",
        product_code=product_code,
        adjust_date=adjust_date,
        summary=summary,
        forms=built,
        count=len(built),
        applied_rule="fulfillment.propose.session_draft",
    ).model_dump()
