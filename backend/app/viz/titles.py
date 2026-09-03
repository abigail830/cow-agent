"""Human-readable auto titles for SQL visualizations."""

from __future__ import annotations

from app.viz.spec import VizIntent, VizKind


def infer_auto_title(
    columns: list[str],
    *,
    intent: VizIntent = "auto",
    kind: VizKind | None = None,
) -> str:
    if not columns:
        return "Query results"
    if len(columns) >= 3 and (intent == "matrix" or kind == "heatmap"):
        return f"{columns[0]} × {columns[1]}"
    if len(columns) >= 2:
        return f"{columns[-1]} by {columns[0]}"
    return f"{columns[0]} summary"
