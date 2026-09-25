"""Pre-parse DOCX structure probe — input-side signals for quality gates."""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree as ET

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_P_TAG = f"{_W_NS}p"
_T_TAG = f"{_W_NS}t"
_TBL_TAG = f"{_W_NS}tbl"
_PSTYLE_TAG = f"{_W_NS}pStyle"
_BR_TAG = f"{_W_NS}br"
_PAGE_BREAK_BEFORE_TAG = f"{_W_NS}pageBreakBefore"
_LAST_RENDERED_PAGE_BREAK_TAG = f"{_W_NS}lastRenderedPageBreak"
_VAL_ATTR = f"{_W_NS}val"
_TYPE_ATTR = f"{_W_NS}type"

_HEADING_STYLE_RE = re.compile(r"^(Heading|Title|Subtitle|TOC)", re.I)
_PAGES_RE = re.compile(r"<Pages>(\d+)</Pages>")


@dataclass(frozen=True)
class DocxProbe:
    file_size: int
    text_chars: int
    paragraph_count: int
    table_count: int
    image_count: int
    heading_style_count: int
    has_legacy_doc: bool
    page_count: int | None = None
    page_break_after_para: tuple[int, ...] = ()

    @property
    def is_large(self) -> bool:
        return self.file_size >= 100_000

    @property
    def is_small(self) -> bool:
        return self.file_size < 32_000


def _paragraph_has_page_break(paragraph: ET.Element) -> bool:
    for node in paragraph.iter():
        tag = node.tag
        if tag == _BR_TAG and node.attrib.get(_TYPE_ATTR) == "page":
            return True
        if tag in (_PAGE_BREAK_BEFORE_TAG, _LAST_RENDERED_PAGE_BREAK_TAG):
            return True
    return False


def _extract_page_count(app_xml: bytes | None) -> int | None:
    if not app_xml:
        return None
    match = _PAGES_RE.search(app_xml.decode("utf-8", errors="ignore"))
    if not match:
        return None
    try:
        pages = int(match.group(1))
        return pages if pages > 0 else None
    except ValueError:
        return None


def _probe_docx_zip(zf: zipfile.ZipFile, *, file_size: int) -> DocxProbe:
    xml_bytes = zf.read("word/document.xml")
    app_xml = None
    if "docProps/app.xml" in zf.namelist():
        app_xml = zf.read("docProps/app.xml")

    root = ET.fromstring(xml_bytes)
    text_chars = 0
    paragraph_count = 0
    table_count = 0
    image_count = 0
    heading_style_count = 0
    page_break_after_para: list[int] = []

    for node in root.iter():
        tag = node.tag
        if tag == _T_TAG and node.text:
            text_chars += len(node.text)
            if node.tail:
                text_chars += len(node.tail)
        elif tag == _P_TAG:
            if _paragraph_has_page_break(node):
                page_break_after_para.append(paragraph_count)
            paragraph_count += 1
            for child in node.iter(_PSTYLE_TAG):
                val = child.attrib.get(_VAL_ATTR, "")
                if _HEADING_STYLE_RE.match(val):
                    heading_style_count += 1
        elif tag == _TBL_TAG:
            table_count += 1
        elif tag.endswith("}drawing") or tag.endswith("}pict"):
            image_count += 1

    return DocxProbe(
        file_size=file_size,
        text_chars=text_chars,
        paragraph_count=paragraph_count,
        table_count=table_count,
        image_count=image_count,
        heading_style_count=heading_style_count,
        has_legacy_doc=False,
        page_count=_extract_page_count(app_xml),
        page_break_after_para=tuple(page_break_after_para),
    )


def probe_docx_bytes(file_bytes: bytes) -> DocxProbe:
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
        return _probe_docx_zip(zf, file_size=len(file_bytes))


def probe_docx_path(path: Path) -> DocxProbe:
    suffix = path.suffix.lower()
    if suffix == ".doc":
        try:
            file_size = path.stat().st_size
        except OSError:
            file_size = 0
        return DocxProbe(
            file_size=file_size,
            text_chars=0,
            paragraph_count=0,
            table_count=0,
            image_count=0,
            heading_style_count=0,
            has_legacy_doc=True,
        )
    with zipfile.ZipFile(path) as zf:
        return _probe_docx_zip(zf, file_size=path.stat().st_size)
