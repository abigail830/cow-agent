"""Webhook trigger payload schemas for yl-worker2.

POST /api/v1/agents/yl-worker2/triggers

Example payload:
{
  "event_type": "base_inbound_delay",
  "product_code": "MOCK_YLP001",
  "adjust_date": "2026-06-30",
  "site_code": "MOCK_WH_B02",
  "detail": {"from_available_before": 8000, "from_available_after": 3200}
}
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "base_inbound_delay",
    "large_order_added",
    "inventory_snapshot_changed",
    "custom",
]


class YlWorker2TriggerPayload(BaseModel):
    event_type: EventType
    product_code: str
    adjust_date: str = Field(description="Snapshot date YYYY-MM-DD")
    site_code: str | None = None
    detail: dict[str, Any] = Field(default_factory=dict)
    source: str = "external"


class YlWorker2TriggerResponse(BaseModel):
    chat_id: str
    agent_slug: str
    initial_message: str
    status: str = "session_created"
