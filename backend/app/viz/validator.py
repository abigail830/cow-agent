"""Validate and repair VizSpec with graceful degradation."""

from __future__ import annotations

from typing import Any

from app.viz.builder import build_spec
from app.viz.spec import VizIntent, VizResult, VizSpec


def _table_fallback(
    rows: list[dict[str, Any]],
    columns: list[str],
    *,
    title: str,
    message: str,
) -> VizResult:
    spec = build_spec(rows, columns, intent="detail", title=title, kind="table")
    if spec is None:
        return VizResult(status="skipped", message=message, fallback_table=rows[:20] or None)
    spec.fallback = True
    return VizResult(
        status="degraded",
        kind="table",
        spec=spec,
        message=message,
        fallback_table=rows[:20],
    )


def validate_spec(
    spec: VizSpec | None,
    rows: list[dict[str, Any]],
    columns: list[str],
    *,
    title: str,
) -> VizResult:
    if spec is None:
        return _table_fallback(
            rows,
            columns,
            title=title,
            message="No suitable visualization; showing table instead.",
        )

    repaired = False

    if spec.kind == "heatmap":
        if (
            len(spec.heatmap_rows) < 2
            or len(spec.heatmap_cols) < 2
            or not spec.heatmap_values
        ):
            return _table_fallback(
                rows,
                columns,
                title=title,
                message="Heatmap requires a 2×2 matrix; degraded to table.",
            )

    if spec.kind in ("bar", "line", "combo"):
        if not spec.x or not spec.series:
            return _table_fallback(
                rows,
                columns,
                title=title,
                message="Chart missing axis data; degraded to table.",
            )
        for s in spec.series:
            if not any(v is not None for v in s.data):
                return _table_fallback(
                    rows,
                    columns,
                    title=title,
                    message="Chart has no numeric values; degraded to table.",
                )

    if spec.kind == "table" and not spec.rows:
        return VizResult(status="skipped", message="No rows to display.", fallback_table=None)

    if not spec.title:
        spec.title = title
        repaired = True

    status = "repaired" if repaired else "rendered"
    return VizResult(status=status, kind=spec.kind, spec=spec, message="Visualization ready.")
