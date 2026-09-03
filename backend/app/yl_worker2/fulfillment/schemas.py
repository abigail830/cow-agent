"""Pydantic schemas for propose_fulfillment_forms tool I/O."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

_ALLOC_TYPE = Literal["forward", "lateral"]


class FulfillmentLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allocation_type: _ALLOC_TYPE = "forward"
    from_site_code: str
    to_site_code: str
    transfer_qty: float = Field(gt=0)
    reason: str = ""
    simulation: dict[str, Any] | None = None
    shipping_remark: str | None = None
    planned_ship_at: str | None = None
    expected_arrival_at: str | None = None
    transit_warehouse: str | None = None
    temp_zone: str | None = None
    merchant_order_no: str | None = None
    source_order_no: str | None = None


class ProposeFulfillmentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_code: str
    adjust_date: str
    lines: list[FulfillmentLineIn] = Field(min_length=1)
    business_unit: str | None = None
    source_order_no: str | None = None
    summary: str = ""


class FulfillmentFormSchema(BaseModel):
    model_config = ConfigDict(extra="allow")

    form_id: str
    status: str
    payload: dict[str, Any]
    context: dict[str, Any]
    fingerprint: str
    fulfillment_item: dict[str, Any] | None = None
    confirmed_at: str | None = None


class FulfillmentProposalResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["proposed", "error"]
    product_code: str | None = None
    adjust_date: str | None = None
    summary: str | None = None
    forms: list[FulfillmentFormSchema] = Field(default_factory=list)
    count: int = 0
    applied_rule: str | None = None
    error: str | None = None
