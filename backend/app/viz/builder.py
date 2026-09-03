"""Build VizSpec payloads from tabular SQL rows."""

from __future__ import annotations

from typing import Any

from app.viz.planner import _column_kind, _is_numeric, suggest_kind
from app.viz.spec import VizColumn, VizIntent, VizKind, VizListItem, VizSeries, VizSpec

_MAX_CHART_POINTS = 60
_MAX_HEATMAP_ROWS = 25
_MAX_HEATMAP_COLS = 20
_MAX_TABLE_ROWS = 100


def _coerce_number(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            return None
    return None


def _pick_columns(
    rows: list[dict[str, Any]], columns: list[str], intent: VizIntent
) -> tuple[str | None, str | None, list[str], str | None, str | None]:
    profile = {col: _column_kind(col, [r.get(col) for r in rows[:20]]) for col in columns}
    time_cols = [c for c, k in profile.items() if k == "time"]
    numeric_cols = [c for c, k in profile.items() if k == "numeric"]
    label_cols = [c for c, k in profile.items() if k in ("label", "other")]

    x_col = time_cols[0] if time_cols else (label_cols[0] if label_cols else columns[0])
    y_cols = numeric_cols or [c for c in columns if c != x_col][-1:]
    row_dim = label_cols[0] if label_cols else columns[0]
    col_dim = label_cols[1] if len(label_cols) > 1 else (columns[1] if len(columns) > 1 else columns[0])
    value_col = numeric_cols[0] if numeric_cols else columns[-1]

    if intent == "matrix" and len(columns) >= 3:
        return row_dim, col_dim, [value_col], row_dim, col_dim
    return x_col, None, y_cols[:3], row_dim, col_dim


def build_spec(
    rows: list[dict[str, Any]],
    columns: list[str],
    *,
    intent: VizIntent = "auto",
    title: str | None = None,
    kind: VizKind | None = None,
) -> VizSpec | None:
    if not rows or not columns:
        return None

    resolved_kind = kind or suggest_kind(rows, columns, intent=intent)
    if resolved_kind is None:
        return None

    display_title = (title or "Query results").strip() or "Query results"
    truncated = len(rows) > _MAX_TABLE_ROWS
    work_rows = rows[:_MAX_TABLE_ROWS]

    if resolved_kind == "table":
        return VizSpec(
            kind="table",
            title=display_title,
            columns=[VizColumn(key=c, label=c) for c in columns],
            rows=work_rows,
            truncated=truncated,
        )

    if resolved_kind == "list":
        title_col = columns[0]
        meta_cols = columns[1:4]
        items = [
            VizListItem(
                title=str(row.get(title_col, "")),
                subtitle=str(row.get(meta_cols[0], "")) if meta_cols else None,
                meta=" · ".join(str(row.get(c, "")) for c in meta_cols[1:]) or None,
            )
            for row in work_rows[:30]
        ]
        return VizSpec(kind="list", title=display_title, items=items, truncated=truncated)

    x_col, _, y_cols, row_dim, col_dim = _pick_columns(work_rows, columns, intent)
    value_col = y_cols[0] if y_cols else columns[-1]

    if resolved_kind == "heatmap":
        row_values: list[str] = []
        col_values: list[str] = []
        matrix: dict[tuple[str, str], float] = {}

        for row in work_rows:
            r = str(row.get(row_dim, ""))
            c = str(row.get(col_dim, ""))
            v = _coerce_number(row.get(value_col))
            if v is None:
                continue
            if r not in row_values:
                row_values.append(r)
            if c not in col_values:
                col_values.append(c)
            matrix[(r, c)] = matrix.get((r, c), 0) + float(v)

        row_values = row_values[:_MAX_HEATMAP_ROWS]
        col_values = col_values[:_MAX_HEATMAP_COLS]
        values = [
            [matrix.get((r, c), 0.0) for c in col_values]
            for r in row_values
        ]
        return VizSpec(
            kind="heatmap",
            title=display_title,
            heatmap_rows=row_values,
            heatmap_cols=col_values,
            heatmap_values=values,
            truncated=truncated,
        )

    # bar / line / combo
    assert x_col is not None
    x_labels: list[str] = []
    x_seen: set[str] = set()
    for row in work_rows:
        label = str(row.get(x_col, ""))
        if label not in x_seen:
            x_seen.add(label)
            x_labels.append(label)
        if len(x_labels) >= _MAX_CHART_POINTS:
            break

    series: list[VizSeries] = []
    for idx, y_col in enumerate(y_cols[:2]):
        data_map = {str(row.get(x_col, "")): _coerce_number(row.get(y_col)) for row in work_rows}
        data = [data_map.get(label) for label in x_labels]
        series.append(
            VizSeries(
                name=y_col,
                type="line" if resolved_kind in ("line", "combo") and idx == len(y_cols) - 1 else "bar",
                data=data,
                y_axis_index=1 if resolved_kind == "combo" and idx > 0 else 0,
            )
        )

    if not series:
        numeric_col = next((c for c in columns if _is_numeric(work_rows[0].get(c))), columns[-1])
        data_map = {str(row.get(x_col, "")): _coerce_number(row.get(numeric_col)) for row in work_rows}
        series = [
            VizSeries(
                name=numeric_col,
                type="bar" if resolved_kind == "bar" else "line",
                data=[data_map.get(label) for label in x_labels],
            )
        ]

    chart_kind: VizKind = resolved_kind if resolved_kind in ("bar", "line", "combo") else "bar"
    return VizSpec(
        kind=chart_kind,
        title=display_title,
        x=x_labels,
        series=series,
        truncated=truncated,
    )
