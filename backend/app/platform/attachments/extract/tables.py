"""Extract xlsx / xls / csv into Markdown tables (no rasterization)."""

from __future__ import annotations

import csv
import io

from app.platform.attachments.extract.text import decode_text_bytes

DEFAULT_MAX_ROWS_PER_SHEET = 2000


def extract_sheet_bytes(
    data: bytes,
    *,
    filename: str = "",
    max_rows_per_sheet: int = DEFAULT_MAX_ROWS_PER_SHEET,
) -> tuple[str, list[str]]:
    name = (filename or "").lower()
    if name.endswith(".csv"):
        return _extract_csv(data, max_rows=max_rows_per_sheet)
    return _extract_workbook(data, max_rows_per_sheet=max_rows_per_sheet)


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("|", "\\|").replace("\n", " ")


def _markdown_table(rows: list[list[str]]) -> str:
    if not rows:
        return "_empty sheet_"
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = normalized[0]
    body = normalized[1:]
    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join("---" for _ in header) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def _extract_csv(data: bytes, *, max_rows: int) -> tuple[str, list[str]]:
    warnings: list[str] = []
    text = decode_text_bytes(data)
    reader = csv.reader(io.StringIO(text))
    rows: list[list[str]] = []
    truncated = False
    for index, raw in enumerate(reader, start=1):
        if index > max_rows:
            truncated = True
            break
        rows.append([_cell_text(cell) for cell in raw])
    if truncated:
        warnings.append(f"CSV truncated after {max_rows} rows")
    if not rows:
        warnings.append("empty spreadsheet")
        return "[empty spreadsheet]", warnings
    return _markdown_table(rows), warnings


def _extract_workbook(data: bytes, *, max_rows_per_sheet: int) -> tuple[str, list[str]]:
    from openpyxl import load_workbook

    warnings: list[str] = []
    workbook = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    sections: list[str] = []
    try:
        for sheet in workbook.worksheets:
            rows: list[list[str]] = []
            truncated = False
            for index, raw in enumerate(sheet.iter_rows(values_only=True), start=1):
                if index > max_rows_per_sheet:
                    truncated = True
                    break
                rows.append([_cell_text(cell) for cell in raw])
            if truncated:
                warnings.append(f"Sheet {sheet.title!r} truncated after {max_rows_per_sheet} rows")
            if not rows:
                sections.append(f"## {sheet.title}\n\n_empty sheet_")
                continue
            sections.append(f"## {sheet.title}\n\n{_markdown_table(rows)}")
    finally:
        workbook.close()
    if not sections:
        warnings.append("empty spreadsheet")
        return "[empty spreadsheet]", warnings
    return "\n\n".join(sections), warnings
