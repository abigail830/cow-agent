"""Declarative visualization specs returned to the frontend."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


VizKind = Literal["table", "list", "bar", "line", "combo", "heatmap"]
VizStatus = Literal["rendered", "repaired", "degraded", "skipped"]
VizIntent = Literal["auto", "trend", "matrix", "ranking", "detail", "none"]


class VizColumn(BaseModel):
    key: str
    label: str | None = None


class VizSeries(BaseModel):
    name: str
    type: Literal["bar", "line"] = "bar"
    data: list[float | int | None]
    y_axis_index: int = 0


class VizListItem(BaseModel):
    title: str
    subtitle: str | None = None
    meta: str | None = None


class VizSpec(BaseModel):
    kind: VizKind
    title: str
    source_call_id: str | None = None
    columns: list[VizColumn] | None = None
    rows: list[dict[str, Any]] | None = None
    items: list[VizListItem] | None = None
    x: list[str] | None = None
    series: list[VizSeries] | None = None
    heatmap_rows: list[str] = Field(default_factory=list)
    heatmap_cols: list[str] = Field(default_factory=list)
    heatmap_values: list[list[float | int]] = Field(default_factory=list)
    fallback: bool = False
    truncated: bool = False


class VizResult(BaseModel):
    status: VizStatus
    kind: str | None = None
    spec: VizSpec | None = None
    message: str = ""
    fallback_table: list[dict[str, Any]] | None = None

    def to_tool_dict(self) -> dict[str, Any]:
        payload = self.model_dump(mode="json", exclude_none=True)
        if self.spec is not None:
            payload["spec"] = self.spec.model_dump(mode="json", exclude_none=True)
        return payload
