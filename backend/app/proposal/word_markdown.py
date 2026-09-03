"""Markdown helpers for Word export — GFM table splitting and Subdoc building."""

from __future__ import annotations

import re
from typing import Any

from docxtpl import DocxTemplate

_TABLE_ROW_RE = re.compile(r"^\|.+\|$")


def markdown_to_plain(text: str) -> str:
    """Strip markdown syntax and collapse soft line-wraps for Word paragraphs."""
    lines: list[str] = []
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            lines.append("")
            continue
        line = re.sub(r"^#+\s*", "", line)
        line = re.sub(r"^\s*[-*+]\s+", "", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"\*(.+?)\*", r"\1", line)
        line = re.sub(r"`(.+?)`", r"\1", line)
        lines.append(line)

    merged: list[str] = []
    current: list[str] = []
    for line in lines:
        if line == "":
            if current:
                merged.append(" ".join(current))
                current = []
            merged.append("")
        else:
            current.append(line)
    if current:
        merged.append(" ".join(current))

    result = re.sub(r"\n{3,}", "\n\n", "\n".join(merged))
    return result.strip()


def _parse_table_row(line: str) -> list[str]:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return []
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def _is_separator_row(line: str) -> bool:
    """True for GFM separator rows such as | --- | or | --- | --- |."""
    cells = _parse_table_row(line.strip())
    if not cells:
        return False
    return all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _is_table_start(lines: list[str], index: int) -> bool:
    if index + 1 >= len(lines):
        return False
    row = lines[index].strip()
    separator = lines[index + 1].strip()
    return bool(_TABLE_ROW_RE.match(row) and _is_separator_row(separator))


def _parse_table_block(table_lines: list[str]) -> dict[str, Any]:
    headers = _parse_table_row(table_lines[0])
    rows: list[list[str]] = []
    for line in table_lines[2:]:
        cells = _parse_table_row(line)
        if cells:
            rows.append(cells)
    return {"type": "table", "headers": headers, "rows": rows}


def split_gfm_markdown(text: str) -> list[dict[str, Any]]:
    """Split markdown into alternating text and GFM table blocks."""
    lines = str(text or "").splitlines()
    blocks: list[dict[str, Any]] = []
    text_buf: list[str] = []
    index = 0

    while index < len(lines):
        if _is_table_start(lines, index):
            if text_buf:
                blocks.append({"type": "text", "raw": "\n".join(text_buf)})
                text_buf = []
            table_lines: list[str] = []
            while index < len(lines):
                stripped = lines[index].strip()
                if not _TABLE_ROW_RE.match(stripped):
                    break
                table_lines.append(lines[index])
                index += 1
            if table_lines:
                blocks.append(_parse_table_block(table_lines))
            continue

        text_buf.append(lines[index])
        index += 1

    if text_buf:
        blocks.append({"type": "text", "raw": "\n".join(text_buf)})
    return blocks


def markdown_has_gfm_table(text: str) -> bool:
    return any(block["type"] == "table" for block in split_gfm_markdown(text))


def _set_cell_text(cell: Any, value: str, *, bold: bool = False) -> None:
    paragraph = cell.paragraphs[0]
    paragraph.text = ""
    run = paragraph.add_run(str(value or ""))
    if bold:
        run.bold = True


def _add_plain_paragraphs(subdoc: Any, text: str) -> None:
    """Render text blocks as Word paragraphs; preserve markdown bullet lines."""
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^[-*+]\s+", line):
            bullet = re.sub(r"^[-*+]\s+", "", line)
            bullet = re.sub(r"\*\*(.+?)\*\*", r"\1", bullet)
            try:
                subdoc.add_paragraph(bullet, style="List Bullet")
            except KeyError:
                subdoc.add_paragraph(f"• {bullet}")
            continue
        plain = markdown_to_plain(line)
        if plain.strip():
            subdoc.add_paragraph(plain.strip())


def _add_gfm_table(subdoc: Any, headers: list[str], rows: list[list[str]]) -> None:
    if not headers:
        return
    col_count = len(headers)
    table = subdoc.add_table(rows=1 + len(rows), cols=col_count)
    table.style = "Table Grid"
    for col_index, header in enumerate(headers):
        _set_cell_text(table.rows[0].cells[col_index], header, bold=True)
    for row_index, row in enumerate(rows):
        for col_index in range(col_count):
            value = row[col_index] if col_index < len(row) else ""
            _set_cell_text(table.rows[row_index + 1].cells[col_index], value)


def build_markdown_subdoc(doc: DocxTemplate, markdown: str) -> Any:
    """Build a docxtpl Subdoc with plain paragraphs and native Word tables."""
    subdoc = doc.new_subdoc()
    for block in split_gfm_markdown(markdown):
        if block["type"] == "text":
            _add_plain_paragraphs(subdoc, block["raw"])
        elif block["type"] == "table":
            _add_gfm_table(subdoc, block["headers"], block["rows"])
    return subdoc


def _attach_subdoc_to_markdown_holder(doc: DocxTemplate, holder: Any) -> None:
    body = str(getattr(holder, "body", "") or "")
    if not body.strip() or not markdown_has_gfm_table(body):
        holder.subdoc = None
        return
    holder.subdoc = build_markdown_subdoc(doc, body)


def attach_markdown_subdocs(doc: DocxTemplate, context: dict[str, Any]) -> None:
    """Populate `.subdoc` on markdown-bearing section objects before render."""
    sections = context.get("sections")
    if not isinstance(sections, dict):
        return
    for section in sections.values():
        if not hasattr(section, "body"):
            continue
        if str(section.body or "").strip():
            _attach_subdoc_to_markdown_holder(doc, section)
        blocks = getattr(section, "blocks", None) or []
        for block in blocks:
            if hasattr(block, "body"):
                _attach_subdoc_to_markdown_holder(doc, block)
