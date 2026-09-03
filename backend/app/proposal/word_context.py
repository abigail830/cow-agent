"""Build structured context for Word template rendering."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from app.proposal.draft import (
    _derive_first_invoice_lines,
    _derive_payment_options,
    _draft_filename,
    _effective_fee_layout,
    _fee_table_render_groups,
    _render_draft_title,
    _sections,
    find_section,
)
from app.proposal.fee_table import format_money, payment_summary_footer, row_total_annualized
from app.proposal.footnotes import apply_footnote_numbers, collect_footnotes
from app.proposal.loaders import load_template_yaml, read_static_block
from app.proposal.placeholders import (
    apply_template_placeholders,
    resolve_section_source_content,
    selected_package_names,
)
from app.proposal.word_markdown import markdown_to_plain as _markdown_to_plain


def _client_facts(draft: dict[str, Any]) -> dict[str, Any]:
    client = (draft.get("facts") or {}).get("client") or {}
    if not isinstance(client, dict):
        return {}
    return {key: value for key, value in client.items() if value not in (None, "")}


def cover_for_name(client: dict[str, Any]) -> str:
    """Company name first; fall back to contact (contract_name)."""
    company = str(client.get("company_name") or "").strip()
    if company:
        return company
    return str(client.get("contract_name") or "").strip()


def _section_body(
    draft: dict[str, Any],
    section: dict[str, Any],
    *,
    template_id: str,
) -> str:
    kind = section.get("kind")
    if kind == "static_block":
        source = section.get("source") or {}
        file_ref = source.get("file")
        if template_id and file_ref:
            try:
                return read_static_block(template_id, str(file_ref)).strip()
            except OSError:
                return ""
        return str(section.get("content") or "").strip()
    if kind == "markdown_block":
        if template_id:
            return resolve_section_source_content(draft, section, template_id=template_id)
        return str(section.get("content") or "").strip()
    if kind == "fee_section":
        intro = section.get("intro") or {}
        if isinstance(intro, dict):
            content = str(intro.get("content") or "").strip()
            if not content and template_id:
                source = intro.get("source") or {}
                file_ref = source.get("file")
                if file_ref:
                    try:
                        content = read_static_block(template_id, str(file_ref)).strip()
                    except OSError:
                        content = ""
            if content:
                return apply_template_placeholders(content, draft, template_id, "fee_table")
        return ""
    if kind == "derived_section":
        intro = section.get("intro") or {}
        if isinstance(intro, dict):
            return str(intro.get("content") or "").strip()
    return ""


def _build_fee_tables(draft: dict[str, Any], section: dict[str, Any]) -> dict[str, Any]:
    groups = _fee_table_render_groups(draft, section)
    layout = _effective_fee_layout(draft, section)
    currency = str(layout.get("currency") or "")
    table_style = str(layout.get("table_style") or "simple")
    all_rows = [row for group in groups for row in group.get("rows") or []]
    footnote_entries = collect_footnotes(all_rows) if layout.get("footnotes") == "aggregate" else []
    if footnote_entries:
        apply_footnote_numbers(all_rows, footnote_entries)
    return {
        "currency": currency,
        "style": table_style,
        "groups": groups,
        "has_groups": bool(groups),
        "footnotes": [
            {"number": entry.number, "text": entry.text}
            for entry in footnote_entries
        ],
    }


def _build_first_invoice(
    draft: dict[str, Any],
    section: dict[str, Any],
) -> dict[str, Any]:
    derivation = section.get("derivation") or {}
    source_section_id = str(derivation.get("source_section") or "solution_and_fees")
    fee_section = find_section(draft, source_section_id)
    if not fee_section or fee_section.get("kind") != "fee_section":
        return {"rows": [], "subtotal": 0.0, "tax": 0.0, "total": 0.0}

    lines = _derive_first_invoice_lines(draft, fee_section, section)
    layout = _effective_fee_layout(draft, fee_section)
    currency = str(layout.get("currency") or "")
    tax_cfg = derivation.get("tax") if isinstance(derivation.get("tax"), dict) else {}
    rate = float(tax_cfg.get("rate") or 0.0)
    tax_label = str(tax_cfg.get("label") or "GST").strip() or "GST"
    rate_display = str(tax_cfg.get("rate_display") or f"{rate * 100:g}%").strip()

    rows: list[dict[str, Any]] = []
    subtotal = 0.0
    tax_total = 0.0
    grand_total = 0.0
    for line in lines:
        price = float(line.get("price") or 0)
        gst = round(price * rate, 2)
        row_total = round(price + gst, 2)
        subtotal += price
        tax_total += gst
        grand_total += row_total
        rows.append(
            {
                "description": str(line.get("label") or "").strip(),
                "price": price,
                "price_display": format_money(price, currency, include_currency=False),
                "tax_display": format_money(gst, currency, include_currency=False),
                "total_display": format_money(row_total, currency, include_currency=False),
            }
        )

    return {
        "currency": currency,
        "tax_label": tax_label,
        "tax_rate_display": rate_display,
        "rows": rows,
        "has_rows": bool(rows),
        "subtotal": subtotal,
        "subtotal_display": format_money(subtotal, currency, include_currency=False),
        "tax": tax_total,
        "tax_display": format_money(tax_total, currency, include_currency=False),
        "total": grand_total,
        "total_display": format_money(grand_total, currency, include_currency=False),
    }


def _build_payment_options(
    draft: dict[str, Any],
    section: dict[str, Any],
) -> dict[str, Any]:
    derivation = section.get("derivation") or {}
    source_section_id = str(derivation.get("source_section") or "solution_and_fees")
    fee_section = find_section(draft, source_section_id)
    if not fee_section or fee_section.get("kind") != "fee_section":
        return {"currency": "", "options": [], "has_options": False}

    options = _derive_payment_options(draft, fee_section, section)
    if not options:
        return {"currency": "", "options": [], "has_options": False}

    layout = _effective_fee_layout(draft, fee_section)
    currency = str(layout.get("currency") or "")
    include_currency = bool(currency)

    built_options: list[dict[str, Any]] = []
    for option in options:
        raw_rows = option.get("rows") or []
        rows: list[dict[str, Any]] = []
        for row in raw_rows:
            total = row.get("total_annualized")
            if total is None:
                total = row_total_annualized(row)
            rows.append(
                {
                    "label": str(row.get("label") or row.get("group_id") or "").strip(),
                    "monthly_display": format_money(
                        row.get("monthly"), currency, include_currency=include_currency
                    ),
                    "quarterly_display": format_money(
                        row.get("quarterly"), currency, include_currency=include_currency
                    ),
                    "annual_display": format_money(
                        row.get("annual"), currency, include_currency=include_currency
                    ),
                    "once_off_display": format_money(
                        row.get("once_off"), currency, include_currency=include_currency
                    ),
                    "total_display": format_money(
                        total, currency, include_currency=include_currency
                    ),
                }
            )
        summary = option.get("summary") or payment_summary_footer(raw_rows)
        built_options.append(
            {
                "option_id": str(option.get("option_id") or ""),
                "label": str(option.get("label") or option.get("option_id") or "Payment Option"),
                "rows": rows,
                "has_rows": bool(rows),
                "summary": {
                    "once_off_total_display": format_money(
                        summary.get("once_off_total"),
                        currency,
                        include_currency=include_currency,
                    ),
                    "recurring_annualized_total_display": format_money(
                        summary.get("recurring_annualized_total"),
                        currency,
                        include_currency=include_currency,
                    ),
                },
            }
        )

    return {
        "currency": currency,
        "options": built_options,
        "has_options": bool(built_options),
    }


class WordSectionIntro:
    def __init__(self, body: str) -> None:
        text = str(body or "")
        self.body = text
        self.plain = _markdown_to_plain(text)
        self.has_content = bool(self.plain.strip())

    def __str__(self) -> str:
        return self.plain


class WordAppendixBlock:
    def __init__(self, *, title: str, body: str, page_break_after: bool) -> None:
        text = str(body or "")
        self.title = title
        self.body = text
        self.plain = _markdown_to_plain(text)
        self.subdoc: Any = None
        self.page_break_after = page_break_after
        self.has_content = bool(text.strip())

    def __str__(self) -> str:
        return self.plain


class WordSectionContext:
    """Section context object so Jinja can use `.items` without hitting dict.items()."""

    def __init__(
        self,
        *,
        enabled: bool,
        title: str,
        body: str,
        intro: WordSectionIntro | None = None,
        blocks: list[WordAppendixBlock] | None = None,
    ) -> None:
        text = str(body or "")
        self.enabled = enabled
        self.title = title
        self.body = text
        self.plain = _markdown_to_plain(text)
        self.subdoc: Any = None
        self.intro = intro or WordSectionIntro("")
        appendix_blocks = blocks or []
        self.blocks = appendix_blocks
        self.items = appendix_blocks
        self.has_content = bool(text.strip()) or bool(appendix_blocks)
        self.has_blocks = bool(appendix_blocks)

    def __str__(self) -> str:
        return self.plain


def resolve_word_text(value: Any) -> str:
    """Coerce section objects / dicts / strings to plain export text."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("plain", "body"):
            nested = value.get(key)
            if nested not in (None, ""):
                return resolve_word_text(nested)
        return ""
    plain = getattr(value, "plain", None)
    if isinstance(plain, str) and plain.strip():
        return plain
    body = getattr(value, "body", None)
    if isinstance(body, str) and body.strip():
        return _markdown_to_plain(body)
    return ""


def _empty_word_section(*, section_id: str, title: str) -> WordSectionContext:
    """Placeholder section so Jinja can safely use sections.<id> in Word templates."""
    return WordSectionContext(
        enabled=False,
        title=title,
        body="",
        intro=WordSectionIntro(""),
        blocks=[],
    )


def _build_sections(draft: dict[str, Any], *, template_id: str) -> dict[str, WordSectionContext]:
    sections: dict[str, WordSectionContext] = {}
    for section in _sections(draft):
        section_id = str(section.get("id") or "").strip()
        if not section_id:
            continue
        enabled = section.get("enabled") is not False
        body = _section_body(draft, section, template_id=template_id) if enabled else ""
        intro: WordSectionIntro | None = None
        appendix_blocks: list[WordAppendixBlock] | None = None
        if section.get("kind") == "fee_section":
            intro_body = _section_body(draft, section, template_id=template_id) if enabled else ""
            intro = WordSectionIntro(intro_body)
        if section.get("kind") == "collection":
            raw_blocks: list[WordAppendixBlock] = []
            for block in section.get("blocks") or []:
                if not isinstance(block, dict) or block.get("enabled") is False:
                    continue
                block_body = _section_body(draft, block, template_id=template_id)
                if not block_body:
                    continue
                raw_blocks.append(
                    WordAppendixBlock(
                        title=str(block.get("title") or block.get("id") or "").strip(),
                        body=block_body,
                        page_break_after=False,
                    )
                )
            for index, block in enumerate(raw_blocks):
                block.page_break_after = index < len(raw_blocks) - 1
            appendix_blocks = raw_blocks
        sections[section_id] = WordSectionContext(
            enabled=enabled,
            title=str(section.get("title") or section_id),
            body=body,
            intro=intro,
            blocks=appendix_blocks,
        )

    tpl = load_template_yaml(template_id) if template_id else {}
    for spec in tpl.get("sections") or []:
        if not isinstance(spec, dict):
            continue
        section_id = str(spec.get("id") or "").strip()
        if not section_id or section_id in sections:
            continue
        sections[section_id] = _empty_word_section(
            section_id=section_id,
            title=str(spec.get("title") or section_id),
        )
    return sections


def build_word_context(draft: dict[str, Any]) -> dict[str, Any]:
    from app.proposal.placeholders import sync_draft_template_placeholders

    sync_draft_template_placeholders(draft)
    template_id = str((draft.get("meta") or {}).get("template_id") or "").strip()
    tpl = load_template_yaml(template_id) if template_id else {}
    client = (draft.get("facts") or {}).get("client") or {}
    if not isinstance(client, dict):
        client = {}

    fee_tables: dict[str, Any] = {"currency": "", "style": "", "groups": [], "footnotes": []}
    first_invoice: dict[str, Any] = {"rows": []}
    payment_options: dict[str, Any] = {"options": [], "has_options": False}
    for section in _sections(draft):
        if section.get("enabled") is False:
            continue
        if section.get("kind") == "fee_section":
            fee_tables = _build_fee_tables(draft, section)
        elif section.get("kind") == "derived_section":
            deriv_type = str((section.get("derivation") or {}).get("type") or "")
            if deriv_type == "first_invoice_from_fee_tables":
                first_invoice = _build_first_invoice(draft, section)
            elif deriv_type == "payment_options_from_fee_tables":
                payment_options = _build_payment_options(draft, section)

    package_names = selected_package_names(draft)
    return {
        "meta": {
            "title": _render_draft_title(tpl, client),
            "date": date.today().isoformat(),
            "template_id": template_id,
            "template_display_name": str(tpl.get("display_name") or template_id),
        },
        "client": _client_facts(draft),
        "cover_for": cover_for_name(client),
        "sections": _build_sections(draft, template_id=template_id),
        "fee_tables": fee_tables,
        "first_invoice": first_invoice,
        "payment_options": payment_options,
        "derived": {
            "selected_packages_bullet_list": (
                "\n".join(f"- {name}" for name in package_names) if package_names else "—"
            ),
        },
    }


def word_export_filename(draft: dict[str, Any]) -> str:
    meta = draft.get("meta") or {}
    title = str(meta.get("title") or "").strip()
    client = (draft.get("facts") or {}).get("client") or {}
    if not isinstance(client, dict):
        client = {}
    cover = cover_for_name(client)

    if title and cover:
        if title == cover or title.endswith(f" - {cover}"):
            stem = title
        else:
            stem = f"{title} - {cover}"
    elif title:
        stem = title
    elif cover:
        stem = cover
    else:
        stem = "proposal"

    safe = re.sub(r'[<>:"/\\|?*]', "-", stem)
    safe = re.sub(r"\s+", " ", safe).strip()
    return f"{safe}.docx" if safe else "proposal.docx"
