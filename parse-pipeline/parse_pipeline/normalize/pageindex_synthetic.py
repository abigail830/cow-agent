"""Build a Document-Mind-compatible pageindex subset from markdown + OOXML probe."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree as ET

from parse_pipeline.quality.docx_probe import DocxProbe

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_P_TAG = f"{_W_NS}p"
_T_TAG = f"{_W_NS}t"
_BR_TAG = f"{_W_NS}br"
_PAGE_BREAK_BEFORE_TAG = f"{_W_NS}pageBreakBefore"
_LAST_RENDERED_PAGE_BREAK_TAG = f"{_W_NS}lastRenderedPageBreak"
_TYPE_ATTR = f"{_W_NS}type"

_TABLE_PIPE_RE = re.compile(r"^\s*\|.*\|\s*$", re.M)
_HTML_TABLE_RE = re.compile(r"<table\b", re.I)
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class SyntheticPageindexResult:
    pageindex: dict[str, Any]
    warnings: tuple[str, ...] = ()


def _paragraph_has_page_break(paragraph: ET.Element) -> bool:
    for node in paragraph.iter():
        tag = node.tag
        if tag == _BR_TAG and node.attrib.get(_TYPE_ATTR) == "page":
            return True
        if tag in (_PAGE_BREAK_BEFORE_TAG, _LAST_RENDERED_PAGE_BREAK_TAG):
            return True
    return False


def _paragraph_text(paragraph: ET.Element) -> str:
    parts: list[str] = []
    for node in paragraph.iter(_T_TAG):
        if node.text:
            parts.append(node.text)
        if node.tail:
            parts.append(node.tail)
    return "".join(parts).strip()


def _anchor_snippets_from_docx(file_bytes: bytes, page_break_after_para: tuple[int, ...]) -> list[str]:
    if not page_break_after_para:
        return []
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        root = ET.fromstring(zf.read("word/document.xml"))

    para_texts: list[str] = []
    break_after: set[int] = set(page_break_after_para)
    para_idx = 0
    for node in root.iter(_P_TAG):
        if para_idx in break_after:
            text = _paragraph_text(node)
            if text:
                para_texts.append(text)
        para_idx += 1
    return para_texts


def _snippet_pattern(snippet: str) -> re.Pattern[str] | None:
    normalized = _WHITESPACE_RE.sub(" ", snippet).strip()
    if len(normalized) < 8:
        return None
    tail = normalized[-80:]
    words = tail.split()
    if len(words) < 2:
        return None
    use_words = words[-6:]
    return re.compile(r"\s+".join(re.escape(word) for word in use_words), re.IGNORECASE | re.DOTALL)


def _find_anchor_offsets(content_md: str, snippets: list[str]) -> tuple[list[int], float]:
    if not snippets:
        return [], 0.0
    offsets: list[int] = []
    cursor = 0
    matched = 0
    for snippet in snippets:
        pattern = _snippet_pattern(snippet)
        if pattern is None:
            continue
        match = pattern.search(content_md, cursor)
        if not match:
            continue
        matched += 1
        offset = match.end()
        offsets.append(offset)
        cursor = offset
    return offsets, matched / len(snippets)


def _line_start_offsets(content_md: str) -> list[int]:
    offsets = [0]
    for match in re.finditer(r"\n", content_md):
        offsets.append(match.end())
    return offsets


def _offset_to_line(offsets: list[int], char_offset: int) -> int:
    line = 1
    for idx, start in enumerate(offsets):
        if start > char_offset:
            break
        line = idx + 1
    return line


def _split_lines_into_pages(content_md: str, page_count: int) -> list[str]:
    lines = content_md.splitlines(keepends=True)
    if not lines:
        return [content_md] if content_md else [""]
    if page_count <= 1:
        return [content_md]
    per_page = max(1, (len(lines) + page_count - 1) // page_count)
    chunks: list[str] = []
    for start in range(0, len(lines), per_page):
        chunks.append("".join(lines[start : start + per_page]))
    while len(chunks) < page_count:
        chunks.append("")
    return chunks[:page_count]


def _split_page_into_blocks(page_content: str) -> list[str]:
    if not page_content:
        return [""]
    parts = re.split(r"(\n\n+)", page_content)
    blocks: list[str] = []
    idx = 0
    while idx < len(parts):
        chunk = parts[idx]
        if not chunk:
            idx += 1
            continue
        if idx + 1 < len(parts) and re.fullmatch(r"\n\n+", parts[idx + 1] or ""):
            blocks.append(chunk + parts[idx + 1])
            idx += 2
        else:
            blocks.append(chunk)
            idx += 1
    return blocks or [page_content]


def _layout_type(block: str) -> str:
    if _HTML_TABLE_RE.search(block):
        return "table"
    if _TABLE_PIPE_RE.search(block):
        return "table"
    return "text"


def _layouts_from_page_chunks(page_chunks: list[str]) -> list[dict[str, Any]]:
    layouts: list[dict[str, Any]] = []
    for page_num, page_content in enumerate(page_chunks, start=1):
        for block in _split_page_into_blocks(page_content):
            layouts.append(
                {
                    "pageNum": page_num,
                    "type": _layout_type(block),
                    "markdownContent": block,
                }
            )
    return layouts


def build_pageindex_from_markdown(
    content_md: str,
    probe: DocxProbe,
    *,
    file_bytes: bytes | None = None,
) -> SyntheticPageindexResult | None:
    if not content_md.strip():
        return None

    warnings: list[str] = []
    page_count = probe.page_count or max(1, len(probe.page_break_after_para) + 1)

    page_chunks: list[str]
    if file_bytes and probe.page_break_after_para:
        snippets = _anchor_snippets_from_docx(file_bytes, probe.page_break_after_para)
        offsets, match_rate = _find_anchor_offsets(content_md, snippets)
        line_offsets = _line_start_offsets(content_md)
        break_lines = sorted({_offset_to_line(line_offsets, offset) for offset in offsets})
        max_page_from_layouts = len(break_lines) + 1
        degraded = match_rate < 0.5 or (probe.page_count and max_page_from_layouts != probe.page_count)
        if degraded:
            warnings.append("pageindex_alignment_degraded")
            page_chunks = _split_lines_into_pages(content_md, page_count)
        else:
            lines = content_md.splitlines(keepends=True)
            boundaries = [0] + break_lines + [len(lines) + 1]
            page_chunks = []
            for start_idx, end_idx in zip(boundaries, boundaries[1:]):
                start_line = max(0, start_idx)
                end_line = min(len(lines), end_idx - 1)
                page_chunks.append("".join(lines[start_line:end_line]))
            if not page_chunks:
                page_chunks = [content_md]
    elif page_count > 1:
        page_chunks = _split_lines_into_pages(content_md, page_count)
        if probe.page_break_after_para:
            warnings.append("pageindex_alignment_degraded")
    else:
        page_chunks = [content_md]

    layouts = _layouts_from_page_chunks(page_chunks)
    pageindex: dict[str, Any] = {
        "layouts": layouts,
        "source": "markitdown_ooxml_pages",
        "page_count_hint": probe.page_count,
    }
    return SyntheticPageindexResult(pageindex=pageindex, warnings=tuple(warnings))
