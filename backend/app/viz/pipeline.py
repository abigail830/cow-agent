"""End-to-end visualization pipeline from SQL rows."""

from __future__ import annotations

from typing import Any

from app.viz.builder import build_spec
from app.viz.spec import VizIntent, VizKind, VizResult
from app.viz.titles import infer_auto_title
from app.viz.validator import validate_spec


def build_viz_from_rows(
    rows: list[dict[str, Any]],
    columns: list[str],
    *,
    intent: VizIntent = "auto",
    title: str | None = None,
    kind: VizKind | None = None,
) -> VizResult:
    if intent == "none":
        return VizResult(status="skipped", message="Visualization skipped by request.")

    if not rows:
        return VizResult(status="skipped", message="No data rows available for visualization.")

    resolved_kind = kind or None
    display_title = (title or infer_auto_title(columns, intent=intent, kind=resolved_kind)).strip()
    if not display_title:
        display_title = infer_auto_title(columns, intent=intent, kind=resolved_kind)
    spec = build_spec(rows, columns, intent=intent, title=display_title, kind=kind)
    return validate_spec(spec, rows, columns, title=display_title)
