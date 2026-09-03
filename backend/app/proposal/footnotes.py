"""Footnote normalization and fee-table aggregation (region-agnostic MDM field)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.proposal.fee_table import escape_html


@dataclass(frozen=True)
class FootnoteEntry:
    number: int
    text: str
    skus: tuple[str, ...]


def normalize_footnote(text: Any) -> str | None:
    if text is None:
        return None
    cleaned = str(text).strip()
    if not cleaned or cleaned.lower() == "nan":
        return None
    return cleaned


def _row_sku(row: dict[str, Any]) -> str:
    source = row.get("source") or {}
    sku = source.get("sku") if isinstance(source, dict) else None
    if sku:
        return str(sku)
    if row.get("sku"):
        return str(row["sku"])
    return str(row.get("id") or "")


def collect_footnotes(rows: list[dict[str, Any]]) -> list[FootnoteEntry]:
    """Dedupe footnotes by text; numbering follows first row appearance."""
    entries: list[FootnoteEntry] = []
    index_by_text: dict[str, int] = {}

    for row in rows:
        text = normalize_footnote(row.get("footnotes"))
        if not text:
            continue
        sku = _row_sku(row)
        if text in index_by_text:
            entry = entries[index_by_text[text]]
            if sku and sku not in entry.skus:
                merged_skus = entry.skus + (sku,)
                entries[index_by_text[text]] = FootnoteEntry(entry.number, entry.text, merged_skus)
            continue
        number = len(entries) + 1
        index_by_text[text] = len(entries)
        entries.append(FootnoteEntry(number, text, (sku,) if sku else ()))

    return entries


# Backward-compatible alias
collect_table_footnotes = collect_footnotes


def apply_footnote_numbers(rows: list[dict[str, Any]], entries: list[FootnoteEntry]) -> None:
    text_to_num = {entry.text: entry.number for entry in entries}
    for row in rows:
        text = normalize_footnote(row.get("footnotes"))
        row["footnote_num"] = text_to_num.get(text) if text else None


def footnote_superscript_html(number: int) -> str:
    return (
        f'<sup class="proposal-fee-ref">'
        f'<a href="#fn-{number}">{number}</a>'
        f"</sup>"
    )


def render_footnotes_footer(entries: list[FootnoteEntry]) -> str:
    if not entries:
        return ""
    items = "".join(
        f'<li id="fn-{entry.number}">{escape_html(entry.text)}</li>' for entry in entries
    )
    return f'<div class="proposal-fee-footnotes"><ol>{items}</ol></div>'
