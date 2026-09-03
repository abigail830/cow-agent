"""Fee table rendering helpers — frequency columns, grouping totals, payment options."""

from __future__ import annotations

import html
import re
from typing import Any


def escape_html(text: str) -> str:
    return html.escape(str(text).strip(), quote=True)


def escape_table_cell(text: str) -> str:
    """Legacy markdown cell helper — pipes must be removed, not escaped, in GFM tables."""
    cleaned = re.sub(r"\s+", " ", str(text).strip())
    return cleaned.replace("|", "/")


def format_scope_html(scope: str) -> str:
    """Render scope_of_work inside a table cell (paragraphs and bullet lists)."""
    raw = str(scope).strip()
    if not raw:
        return ""

    lines = [ln.strip() for ln in re.split(r"\r?\n", raw) if ln.strip()]
    if not lines:
        return ""

    bullet_prefix = re.compile(r"^[-*•]\s+")
    bullets = [bullet_prefix.sub("", ln) for ln in lines if bullet_prefix.match(ln)]
    prose = [ln for ln in lines if not bullet_prefix.match(ln)]

    if not bullets and len(lines) == 1:
        single = lines[0]
        if ":" in single and any(token in single.lower() for token in ("including", "covering", "such as")):
            head, tail = single.split(":", 1)
            segments = [seg.strip() for seg in re.split(r";|\n", tail) if seg.strip()]
            if len(segments) > 1:
                items = "".join(f"<li>{escape_html(seg)}</li>" for seg in segments)
                return f"<p><strong>{escape_html(head.strip())}:</strong></p><ul>{items}</ul>"

    parts: list[str] = []
    if prose:
        parts.append(f"<p>{escape_html(' '.join(prose))}</p>")
    if bullets:
        items = "".join(f"<li>{escape_html(item)}</li>" for item in bullets)
        parts.append(f"<ul>{items}</ul>")
    return "".join(parts)


def build_service_cell_html(
    index: int,
    sub: int,
    label: str,
    *,
    scope: str | None = None,
    note: str | None = None,
) -> str:
    parts = [f"<strong>{escape_html(f'{index}.{sub} {label}')}</strong>"]
    if scope:
        scope_html = format_scope_html(scope)
        if scope_html:
            parts.append(scope_html)
    if note:
        parts.append(f"<p><em>{escape_html(note)}</em></p>")
    return "".join(parts)


def service_column_flags(layout: dict[str, Any]) -> dict[str, bool]:
    """Resolve which MDM text fields appear in the fee-table Service cell."""
    cols = layout.get("service_columns")
    if isinstance(cols, dict):
        return {
            "service_name": bool(cols.get("service_name", True)),
            "description": bool(cols.get("description", False)),
            "scope_of_work": bool(cols.get("scope_of_work", False)),
        }
    # Legacy: include_scope_of_work maps to scope_of_work only.
    return {
        "service_name": True,
        "description": False,
        "scope_of_work": bool(layout.get("include_scope_of_work")),
    }


def build_fee_service_cell_html(
    row: dict[str, Any],
    columns: dict[str, bool],
    *,
    numbered_prefix: str | None = None,
) -> str:
    """Build service cell HTML from a render DTO (display-driven) or legacy flat row."""
    display = row.get("display") if isinstance(row.get("display"), dict) else {}
    if display.get("preview_primary") or display.get("scope_of_work_display"):
        return build_service_cell_from_display(row, columns, numbered_prefix=numbered_prefix)

    name = str(row.get("service_name") or row.get("label") or "").strip()
    desc = str(row.get("description") or "").strip()
    sow = str(row.get("scope_of_work") or "").strip()

    if columns.get("service_name") and name:
        heading = name
    elif columns.get("description") and desc:
        heading = desc
    else:
        heading = str(row.get("sku") or "")

    parts: list[str] = []
    title = f"{numbered_prefix} {heading}" if numbered_prefix else heading
    parts.append(f"<strong>{escape_html(title)}</strong>")

    if columns.get("description") and desc and desc != heading:
        parts.append(f"<p>{escape_html(desc)}</p>")
    if columns.get("scope_of_work") and sow:
        scope_html = format_scope_html(sow)
        if scope_html:
            parts.append(scope_html)

    result = "".join(parts)
    footnote_num = row.get("footnote_num")
    if footnote_num:
        from app.proposal.footnotes import footnote_superscript_html

        result += footnote_superscript_html(int(footnote_num))
    return result


def build_service_cell_from_display(
    row: dict[str, Any],
    columns: dict[str, bool],
    *,
    numbered_prefix: str | None = None,
) -> str:
    display = row.get("display") if isinstance(row.get("display"), dict) else {}
    heading = str(display.get("preview_primary") or row.get("preview_primary") or row.get("sku") or "").strip()
    sow = str(display.get("scope_of_work_display") or "").strip()

    title = f"{numbered_prefix} {heading}" if numbered_prefix else heading
    parts = [f"<strong>{escape_html(title)}</strong>"]
    if columns.get("scope_of_work") and sow:
        scope_html = format_scope_html(sow)
        if scope_html:
            parts.append(scope_html)

    result = "".join(parts)
    footnote_num = row.get("footnote_num")
    if footnote_num:
        from app.proposal.footnotes import footnote_superscript_html

        result += footnote_superscript_html(int(footnote_num))
    return result


def row_frequency_columns(row: dict[str, Any]) -> dict[str, float | None]:
    amount = row.get("amount")
    if amount is None:
        return {"monthly": None, "quarterly": None, "annual": None, "once_off": None}
    freq = str(row.get("billing_frequency") or "ONE_TIME").upper()
    value = float(amount)
    cols = {"monthly": None, "quarterly": None, "annual": None, "once_off": None}
    if freq == "MONTHLY":
        cols["monthly"] = value
    elif freq == "QUARTERLY":
        cols["quarterly"] = value
    elif freq == "ANNUALLY":
        cols["annual"] = value
    else:
        cols["once_off"] = value
    return cols


_DEFAULT_COLUMN_WIDTHS: dict[str, dict[str, str]] = {
    "simple": {"service": "68%", "amount": "32%"},
    "frequency_columns": {"service": "33.333%", "amount": "13.333%"},
    "one_off_recurring": {"service": "50%", "one_off": "25%", "recurring": "25%"},
}
_TABLE_STYLE = "width:100%;table-layout:fixed;border-collapse:collapse"


def fee_column_widths(layout: dict[str, Any] | None, table_style: str) -> dict[str, str]:
    """Resolve column widths for a fee table style from template/draft fee_layout."""
    style = str(table_style or "simple").strip().lower()
    if style not in _DEFAULT_COLUMN_WIDTHS:
        style = "simple"
    defaults = _DEFAULT_COLUMN_WIDTHS[style]
    raw = (layout or {}).get("column_widths") or {}
    nested: dict[str, Any] = {}
    if isinstance(raw.get(style), dict):
        nested = raw[style]
    flat: dict[str, str] = {}
    for key in defaults:
        if isinstance(raw.get(key), str):
            flat[key] = str(raw[key])
    return {
        key: str(nested.get(key) or flat.get(key) or defaults[key])
        for key in defaults
    }


def format_money(amount: float | None, currency: str = "", *, include_currency: bool = True) -> str:
    if amount is None:
        return ""
    prefix = f"{currency} " if include_currency and currency else ""
    return f"{prefix}${amount:,.2f}"


def row_total_amount(row: dict[str, Any]) -> float | None:
    cols = row.get("frequency_columns") or row_frequency_columns(row)
    values = [cols.get("monthly"), cols.get("quarterly"), cols.get("annual"), cols.get("once_off")]
    present = [float(v) for v in values if v is not None]
    if not present:
        return None
    return sum(present)


def row_annualized_total_amount(row: dict[str, Any]) -> float | None:
    """Annualised total for one service row from price.amount and billing frequency."""
    amount = row.get("amount")
    if amount is None:
        return None
    value = float(amount)
    freq = str(row.get("billing_frequency") or "ONE_TIME").upper()
    if freq == "MONTHLY":
        return value * 12
    if freq == "QUARTERLY":
        return value * 4
    return value


def sum_group_columns(rows: list[dict[str, Any]]) -> dict[str, float]:
    totals = {"monthly": 0.0, "quarterly": 0.0, "annual": 0.0, "once_off": 0.0}
    for row in rows:
        cols = row.get("frequency_columns") or row_frequency_columns(row)
        for key in totals:
            value = cols.get(key)
            if value is not None:
                totals[key] += float(value)
    return totals


def row_total_annualized(cols: dict[str, float | None]) -> float:
    monthly = float(cols.get("monthly") or 0)
    quarterly = float(cols.get("quarterly") or 0)
    annual = float(cols.get("annual") or 0)
    once_off = float(cols.get("once_off") or 0)
    return monthly * 12 + quarterly * 4 + annual + once_off


def recurring_annualized(cols: dict[str, float | None]) -> float:
    monthly = float(cols.get("monthly") or 0)
    quarterly = float(cols.get("quarterly") or 0)
    annual = float(cols.get("annual") or 0)
    return monthly * 12 + quarterly * 4 + annual


def payment_summary_footer(rows: list[dict[str, Any]]) -> dict[str, float]:
    once_off = sum(float(row.get("once_off") or 0) for row in rows)
    recurring = sum(recurring_annualized(row) for row in rows)
    return {"once_off_total": once_off, "recurring_annualized_total": recurring}


def _amount_cell(
    amount: float | None,
    currency: str,
    *,
    include_currency: bool = False,
    compact_layout: bool = False,
    col_width: str | None = None,
) -> str:
    text = format_money(amount, currency, include_currency=include_currency)
    if compact_layout and col_width:
        return (
            f"<td width=\"{col_width}\" class=\"proposal-fee-amount\" "
            f"style=\"width:{col_width}\">"
            f"{escape_html(text) if text else '&nbsp;'}</td>"
        )
    if col_width:
        return (
            f"<td width=\"{col_width}\" class=\"proposal-fee-amount\" style=\"width:{col_width}\">"
            f"{escape_html(text) if text else '&nbsp;'}</td>"
        )
    return f"<td class=\"proposal-fee-amount\">{escape_html(text) if text else '&nbsp;'}</td>"


def _text_amount_cell(
    text: str | None,
    *,
    compact_layout: bool = False,
    col_width: str | None = None,
) -> str:
    value = str(text or "").strip()
    if compact_layout and col_width:
        return (
            f"<td width=\"{col_width}\" class=\"proposal-fee-amount\" "
            f"style=\"width:{col_width}\">"
            f"{escape_html(value) if value else '&nbsp;'}</td>"
        )
    if col_width:
        return (
            f"<td width=\"{col_width}\" class=\"proposal-fee-amount\" style=\"width:{col_width}\">"
            f"{escape_html(value) if value else '&nbsp;'}</td>"
        )
    return f"<td class=\"proposal-fee-amount\">{escape_html(value) if value else '&nbsp;'}</td>"


def _active_frequency_column(billing_frequency: str | None) -> str:
    freq = str(billing_frequency or "ONE_TIME").upper()
    if freq == "MONTHLY":
        return "monthly"
    if freq == "QUARTERLY":
        return "quarterly"
    if freq == "ANNUALLY":
        return "annual"
    return "once_off"


def _frequency_row_display(row: dict[str, Any]) -> tuple[dict[str, str | None], str | None, str | None]:
    """Return display frequency columns, optional active-column fee_raw text, and total display."""
    display = row.get("display") if isinstance(row.get("display"), dict) else {}
    freq_display = display.get("frequency_columns_display")
    if isinstance(freq_display, dict):
        return (
            {key: str(freq_display.get(key) or "").strip() or None for key in ("monthly", "quarterly", "annual", "once_off")},
            None,
            str(display.get("total_display") or row.get("amount_display") or "").strip() or None,
        )

    from app.proposal.pricing_rules import normalize_pricing_type, uses_fee_raw_display

    cols = row.get("frequency_columns") or row_frequency_columns(row)
    fee_raw_text = None
    if uses_fee_raw_display(normalize_pricing_type(row.get("pricing_type"))):
        display_text = str(row.get("amount_display") or "").strip()
        if display_text:
            fee_raw_text = display_text
    total = str(row.get("amount_display") or "").strip() or None
    return (
        {
            key: None
            for key in ("monthly", "quarterly", "annual", "once_off")
        },
        fee_raw_text,
        total,
    )


def _fee_table_colgroup(service_width: str, amount_width: str) -> str:
    amount_col = (
        f'<col width="{amount_width}" style="width:{amount_width}" '
        f'class="proposal-fee-col-amount" />'
    )
    return (
        "<colgroup>"
        f'<col width="{service_width}" style="width:{service_width}" '
        f'class="proposal-fee-col-label" />'
        f"{amount_col * 5}"
        "</colgroup>"
    )


def _simple_table_colgroup(service_width: str, amount_width: str) -> str:
    return (
        "<colgroup>"
        f'<col width="{service_width}" style="width:{service_width}" '
        f'class="proposal-fee-col-label" />'
        f'<col width="{amount_width}" style="width:{amount_width}" '
        f'class="proposal-fee-col-amount" />'
        "</colgroup>"
    )


def _fee_table_head(label: str, service_width: str, amount_width: str) -> str:
    return (
        "<thead><tr>"
        f'<th width="{service_width}" style="width:{service_width}">{label}</th>'
        f'<th width="{amount_width}" style="width:{amount_width}" '
        f'class="proposal-fee-amount-head">Monthly</th>'
        f'<th width="{amount_width}" style="width:{amount_width}" '
        f'class="proposal-fee-amount-head">Quarterly</th>'
        f'<th width="{amount_width}" style="width:{amount_width}" '
        f'class="proposal-fee-amount-head">Annual</th>'
        f'<th width="{amount_width}" style="width:{amount_width}" '
        f'class="proposal-fee-amount-head">Once-Off</th>'
        f'<th width="{amount_width}" style="width:{amount_width}" '
        f'class="proposal-fee-amount-head">Total</th>'
        "</tr></thead><tbody>"
    )


def _payment_table_head() -> str:
    return (
        "<thead><tr>"
        "<th>Option</th>"
        "<th>Monthly Fees</th>"
        "<th>Quarterly Fees</th>"
        "<th>Annual Fees</th>"
        "<th>Once-Off Fees</th>"
        "<th>Total Fees (Annualised)</th>"
        "</tr></thead><tbody>"
    )


def _format_amount_cell_text(amount_text: str) -> str:
    return escape_html(amount_text)


def render_frequency_table(
    groups: list[dict[str, Any]],
    *,
    currency: str = "",
    service_columns: dict[str, bool] | None = None,
    column_widths: dict[str, str] | None = None,
) -> str:
    widths = column_widths or fee_column_widths(None, "frequency_columns")
    service_width = widths["service"]
    amount_width = widths["amount"]
    columns = service_columns or {
        "service_name": True,
        "description": False,
        "scope_of_work": False,
    }
    parts: list[str] = []
    for index, group in enumerate(groups, 1):
        title = group.get("display_name") or group.get("group_id") or f"{index}. Services"
        heading = f"### {index}. {title}" if not str(title).startswith(f"{index}.") else f"### {title}"
        parts.append(heading)
        parts.append("")
        parts.append(
            f"<table class=\"proposal-fee-table proposal-fee-table-frequency\" style=\"{_TABLE_STYLE}\">"
        )
        parts.append(_fee_table_colgroup(service_width, amount_width))
        parts.append(_fee_table_head("Service", service_width, amount_width))
        sub = 1
        for row in group.get("rows") or []:
            freq_display, fee_raw_text, total_display = _frequency_row_display(row)
            display = row.get("display") if isinstance(row.get("display"), dict) else {}
            freq_display_map = display.get("frequency_columns_display")
            use_display_only = isinstance(freq_display_map, dict)

            active_col = _active_frequency_column(row.get("billing_frequency"))
            row_currency = str(row.get("currency") or currency)
            service_html = build_fee_service_cell_html(
                row,
                columns,
                numbered_prefix=f"{index}.{sub}",
            )

            def _frequency_cell(column: str) -> str:
                if use_display_only:
                    text = freq_display.get(column)
                    return _text_amount_cell(text, compact_layout=True, col_width=amount_width)
                if fee_raw_text and column == active_col:
                    return _text_amount_cell(fee_raw_text, compact_layout=True, col_width=amount_width)
                if fee_raw_text:
                    return _text_amount_cell(None, compact_layout=True, col_width=amount_width)
                cols = row.get("frequency_columns") or row_frequency_columns(row)
                return _amount_cell(
                    cols.get(column),
                    row_currency,
                    include_currency=bool(row_currency),
                    compact_layout=True,
                    col_width=amount_width,
                )

            if total_display:
                total_cell = _format_amount_cell_text(total_display)
            else:
                annualized_total = row_annualized_total_amount(row)
                total_cell = _format_amount_cell_text(
                    format_money(
                        annualized_total,
                        row_currency,
                        include_currency=bool(row_currency),
                    ).strip()
                    if annualized_total is not None
                    else "",
                )
            parts.append(
                "<tr>"
                f"<td width=\"{service_width}\" class=\"proposal-fee-service\" "
                f"style=\"width:{service_width}\">{service_html}</td>"
                + _frequency_cell("monthly")
                + _frequency_cell("quarterly")
                + _frequency_cell("annual")
                + _frequency_cell("once_off")
                + (
                    f"<td width=\"{amount_width}\" class=\"proposal-fee-amount\" "
                    f"style=\"width:{amount_width}\">{total_cell or '&nbsp;'}</td>"
                )
                + "</tr>"
            )
            sub += 1
        parts.append("</tbody></table>")
        parts.append("")
    return "\n".join(parts).strip()


def _one_off_recurring_colgroup(service_width: str, one_off_width: str, recurring_width: str) -> str:
    return (
        "<colgroup>"
        f'<col width="{service_width}" style="width:{service_width}" '
        f'class="proposal-fee-col-label" />'
        f'<col width="{one_off_width}" style="width:{one_off_width}" '
        f'class="proposal-fee-col-once-off" />'
        f'<col width="{recurring_width}" style="width:{recurring_width}" '
        f'class="proposal-fee-col-recurring" />'
        "</colgroup>"
    )


def _one_off_recurring_column_labels(layout: dict[str, Any] | None) -> dict[str, str]:
    defaults = {
        "service": "Scope",
        "one_off": "One-off",
        "recurring": "Recurring",
    }
    raw = (layout or {}).get("column_labels") or {}
    nested: dict[str, Any] = {}
    if isinstance(raw.get("one_off_recurring"), dict):
        nested = raw["one_off_recurring"]
    return {
        key: str(nested.get(key) or raw.get(key) or defaults[key])
        for key in defaults
    }


def render_one_off_recurring_table(
    groups: list[dict[str, Any]],
    *,
    service_columns: dict[str, bool] | None = None,
    column_widths: dict[str, str] | None = None,
    column_labels: dict[str, str] | None = None,
    empty_cell: str = "-",
) -> str:
    widths = column_widths or fee_column_widths(None, "one_off_recurring")
    service_width = widths["service"]
    one_off_width = widths["one_off"]
    recurring_width = widths["recurring"]
    labels = column_labels or _one_off_recurring_column_labels(None)
    columns = service_columns or {
        "service_name": True,
        "description": False,
        "scope_of_work": True,
    }
    empty = str(empty_cell or "-").strip() or "-"
    parts: list[str] = []
    for group in groups:
        parts.append(f"### {group.get('display_name') or group.get('group_id')}")
        parts.append("")
        parts.append(
            f"<table class=\"proposal-fee-table proposal-fee-table-one-off-recurring\" "
            f"style=\"{_TABLE_STYLE}\">"
        )
        parts.append(_one_off_recurring_colgroup(service_width, one_off_width, recurring_width))
        parts.append(
            "<thead><tr>"
            f'<th width="{service_width}" style="width:{service_width}">{escape_html(labels["service"])}</th>'
            f'<th width="{one_off_width}" style="width:{one_off_width}" '
            f'class="proposal-fee-amount-head">{escape_html(labels["one_off"])}</th>'
            f'<th width="{recurring_width}" style="width:{recurring_width}" '
            f'class="proposal-fee-amount-head">{escape_html(labels["recurring"])}</th>'
            "</tr></thead><tbody>"
        )
        for row in group.get("rows") or []:
            display = row.get("display") if isinstance(row.get("display"), dict) else {}
            once_off = str(display.get("once_off_display") or "").strip() or empty
            recurring = str(display.get("recurring_display") or "").strip() or empty
            service_html = build_fee_service_cell_html(row, columns)
            parts.append(
                "<tr>"
                f"<td width=\"{service_width}\" class=\"proposal-fee-service\" "
                f"style=\"width:{service_width}\">{service_html}</td>"
                + _text_amount_cell(once_off, col_width=one_off_width)
                + _text_amount_cell(recurring, col_width=recurring_width)
                + "</tr>"
            )
        parts.append("</tbody></table>")
        parts.append("")
    return "\n".join(parts).strip()


def render_fee_table_by_style(
    table_style: str,
    groups: list[dict[str, Any]],
    *,
    layout: dict[str, Any] | None = None,
    currency: str = "",
    service_columns: dict[str, bool] | None = None,
    column_widths: dict[str, str] | None = None,
) -> str:
    """Dispatch fee table HTML rendering by draft/template table_style."""
    style = str(table_style or "simple").strip().lower()
    fee_layout = layout or {}
    if style == "frequency_columns":
        return render_frequency_table(
            groups,
            currency=currency,
            service_columns=service_columns,
            column_widths=column_widths,
        )
    if style == "one_off_recurring":
        return render_one_off_recurring_table(
            groups,
            service_columns=service_columns,
            column_widths=column_widths,
            column_labels=_one_off_recurring_column_labels(fee_layout),
            empty_cell=str(fee_layout.get("empty_cell") or "-"),
        )
    return render_simple_table(
        groups,
        show_recurring=fee_layout.get("show_recurring", True),
        service_columns=service_columns,
        amount_column_label=str(fee_layout.get("amount_column_label") or "Amount"),
        column_widths=column_widths,
    )


def render_simple_table(
    groups: list[dict[str, Any]],
    *,
    show_recurring: bool = True,
    service_columns: dict[str, bool] | None = None,
    amount_column_label: str = "Amount",
    column_widths: dict[str, str] | None = None,
) -> str:
    widths = column_widths or fee_column_widths(None, "simple")
    service_width = widths["service"]
    amount_width = widths["amount"]
    columns = service_columns or {
        "service_name": True,
        "description": False,
        "scope_of_work": False,
    }
    parts: list[str] = []
    amount_header = escape_html(amount_column_label)
    for group in groups:
        parts.append(f"### {group.get('display_name') or group.get('group_id')}")
        parts.append("")
        parts.append(
            f"<table class=\"proposal-fee-table proposal-fee-table-simple\" style=\"{_TABLE_STYLE}\">"
        )
        parts.append(_simple_table_colgroup(service_width, amount_width))
        parts.append(
            "<thead><tr>"
            f'<th width="{service_width}" style="width:{service_width}">Service</th>'
            f'<th width="{amount_width}" style="width:{amount_width}">{amount_header}</th>'
            "</tr></thead><tbody>"
        )
        for row in group.get("rows") or []:
            display = row.get("display") if isinstance(row.get("display"), dict) else {}
            amount_text = str(display.get("amount_display") or row.get("amount_display") or "").strip()
            if not amount_text:
                amount = row.get("amount")
                if amount is None:
                    amount_text = str(row.get("status") or "TBD")
                else:
                    row_currency = row.get("currency") or ""
                    amount_text = format_money(float(amount), row_currency, include_currency=bool(row_currency)).strip()
            service_html = build_fee_service_cell_html(row, columns)
            amount_html = _format_amount_cell_text(amount_text)
            parts.append(
                "<tr>"
                f"<td width=\"{service_width}\" class=\"proposal-fee-service\" "
                f"style=\"width:{service_width}\">{service_html}</td>"
                f'<td width="{amount_width}" class="proposal-fee-amount" '
                f'style="width:{amount_width}">{amount_html}</td>'
                "</tr>"
            )
        parts.append("</tbody></table>")
        parts.append("")
    return "\n".join(parts).strip()


def render_first_invoice_table(
    lines: list[dict[str, Any]],
    *,
    currency: str = "",
    tax: dict[str, Any] | None = None,
) -> str:
    if not lines:
        return "_No eligible services for first invoice estimate._"

    tax_cfg = tax or {}
    rate = float(tax_cfg.get("rate") or 0.0)
    tax_label = str(tax_cfg.get("label") or "GST").strip() or "GST"
    rate_display = str(tax_cfg.get("rate_display") or f"{rate * 100:g}%").strip()
    currency_suffix = f" ({currency})" if currency else ""

    parts: list[str] = [
        '<table class="proposal-fee-table proposal-first-invoice-table">',
        "<thead><tr>",
        "<th>Services</th>",
        f"<th>Price{currency_suffix}</th>",
        f"<th>{escape_html(tax_label)}{escape_html(currency_suffix)} ({escape_html(rate_display)})</th>",
        f"<th>Total{currency_suffix}</th>",
        "</tr></thead><tbody>",
    ]

    total_price = 0.0
    total_gst = 0.0
    total_grand = 0.0
    for line in lines:
        price = float(line.get("price") or 0)
        gst = round(price * rate, 2)
        row_total = round(price + gst, 2)
        total_price += price
        total_gst += gst
        total_grand += row_total
        service = str(line.get("label") or "").strip()
        parts.append(
            "<tr>"
            f"<td>{escape_html(service)}</td>"
            f"<td class=\"proposal-fee-amount\">{escape_html(format_money(price, currency, include_currency=False))}</td>"
            f"<td class=\"proposal-fee-amount\">{escape_html(format_money(gst, currency, include_currency=False))}</td>"
            f"<td class=\"proposal-fee-amount\">{escape_html(format_money(row_total, currency, include_currency=False))}</td>"
            "</tr>"
        )

    parts.append(
        "<tr class=\"proposal-fee-summary\">"
        f"<td><strong>Total</strong></td>"
        f"<td class=\"proposal-fee-amount\"><strong>{escape_html(format_money(total_price, currency, include_currency=False))}</strong></td>"
        f"<td class=\"proposal-fee-amount\"><strong>{escape_html(format_money(total_gst, currency, include_currency=False))}</strong></td>"
        f"<td class=\"proposal-fee-amount\"><strong>{escape_html(format_money(total_grand, currency, include_currency=False))}</strong></td>"
        "</tr>"
    )
    parts.append("</tbody></table>")
    return "\n".join(parts)


def render_payment_options_table(options: list[dict[str, Any]], *, currency: str = "") -> str:
    if not options:
        return "_No payment options configured._"

    parts: list[str] = []
    for option in options:
        label = option.get("label") or option.get("option_id") or "Payment Option"
        parts.append(f"### {label}")
        parts.append("")
        parts.append("<table class=\"proposal-fee-table proposal-payment-table\">")
        parts.append(_payment_table_head())
        rows = option.get("rows") or []
        for index, row in enumerate(rows, 1):
            row_label = row.get("label") or row.get("group_id") or f"{index}."
            total = row.get("total_annualized")
            if total is None:
                total = row_total_annualized(row)
            parts.append(
                "<tr>"
                f"<td>{escape_html(str(row_label))}</td>"
                + _amount_cell(row.get("monthly"), currency, include_currency=bool(currency))
                + _amount_cell(row.get("quarterly"), currency, include_currency=bool(currency))
                + _amount_cell(row.get("annual"), currency, include_currency=bool(currency))
                + _amount_cell(row.get("once_off"), currency, include_currency=bool(currency))
                + _amount_cell(total, currency, include_currency=bool(currency))
                + "</tr>"
            )
        summary = option.get("summary") or payment_summary_footer(rows)
        once_off = format_money(summary.get("once_off_total"), currency, include_currency=bool(currency))
        recurring = format_money(summary.get("recurring_annualized_total"), currency, include_currency=bool(currency))
        parts.append(
            f"<tr class=\"proposal-fee-summary\">"
            f"<td colspan=\"5\">Once-Off Fees</td>"
            f"<td class=\"proposal-fee-amount\">{escape_html(once_off)}</td>"
            "</tr>"
        )
        parts.append(
            f"<tr class=\"proposal-fee-summary\">"
            f"<td colspan=\"5\">"
            "<strong>Annualised Total Fees</strong> "
            "<em>(billed on completion, with monthly, quarterly and annual fees associated)</em>"
            "</td>"
            f"<td class=\"proposal-fee-amount\"><strong>{escape_html(recurring)}</strong></td>"
            "</tr>"
        )
        parts.append("</tbody></table>")
        parts.append("")
    return "\n".join(parts).strip()
