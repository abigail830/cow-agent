"""Render Word documents from template files and export context."""

from __future__ import annotations

import random
import re
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate
from jinja2 import Environment

# ── duplicate-ID patterns ────────────────────────────────────────────────────
# w14:paraId / w14:textId are per-paragraph revision IDs; duplicated when
# docxtpl copies {%tr for %} rows.
_PARA_ID_RE = re.compile(r'w14:paraId="([A-F0-9]{8})"', re.IGNORECASE)
_TEXT_ID_RE = re.compile(r'w14:textId="([A-F0-9]{8})"', re.IGNORECASE)

# Drawing / shape IDs (wp:docPr, pic:cNvPr, p:cNvPr) must be unique.
# NOTE: w:bookmarkStart/End share the same id by design — do NOT touch them.
_DRAWING_ID_RE = re.compile(
    r'(<(?:wp:docPr|pic:cNvPr|p:cNvPr)\b[^>]*?\bid=")(\d+)(")',
)


# ── deduplication helpers ────────────────────────────────────────────────────

def _dedup_hex_attr(xml: str, pattern: re.Pattern[str], attr_name: str) -> str:
    seen: set[str] = set()

    def _repl(m: re.Match[str]) -> str:
        val = m.group(1).upper()
        if val not in seen:
            seen.add(val)
            return m.group(0)
        while True:
            fresh = f"{uuid.uuid4().int & 0xFFFFFFFF:08X}"
            if fresh not in seen:
                seen.add(fresh)
                return f'{attr_name}="{fresh}"'

    return pattern.sub(_repl, xml)


def _dedup_drawing_ids(xml: str) -> str:
    seen: set[str] = set()

    def _repl(m: re.Match[str]) -> str:
        val = m.group(2)
        if val not in seen:
            seen.add(val)
            return m.group(0)
        while True:
            fresh = str(random.randint(1_000, 2_000_000_000))
            if fresh not in seen:
                seen.add(fresh)
                return m.group(1) + fresh + m.group(3)

    return _DRAWING_ID_RE.sub(_repl, xml)


def _sanitize_document_xml(xml: str) -> str:
    """Fix duplicate IDs introduced by docxtpl {%tr for %} row duplication."""
    if "w14:paraId" in xml:
        xml = _dedup_hex_attr(xml, _PARA_ID_RE, "w14:paraId")
    if "w14:textId" in xml:
        xml = _dedup_hex_attr(xml, _TEXT_ID_RE, "w14:textId")
    if "wp:docPr" in xml or "pic:cNvPr" in xml or "p:cNvPr" in xml:
        xml = _dedup_drawing_ids(xml)
    return xml


def sanitize_docx_bytes(docx_bytes: bytes) -> bytes:
    """Patch duplicate XML IDs in the rendered document.xml only."""
    inp = BytesIO(docx_bytes)
    out = BytesIO()
    with zipfile.ZipFile(inp, "r") as zin, zipfile.ZipFile(out, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == "word/document.xml":
                data = _sanitize_document_xml(data.decode("utf-8")).encode("utf-8")
            new_info = zipfile.ZipInfo(filename=info.filename, date_time=info.date_time)
            new_info.compress_type = zipfile.ZIP_DEFLATED
            zout.writestr(new_info, data)
    return out.getvalue()


from app.proposal.word_markdown import attach_markdown_subdocs


def render_word_document(template_path: Path, context: dict[str, Any]) -> bytes:
    """Render a docxtpl Word template with plain-string and Subdoc context."""
    doc = DocxTemplate(str(template_path))
    attach_markdown_subdocs(doc, context)
    jinja_env = Environment(autoescape=False)
    doc.render(context, jinja_env=jinja_env)
    buf = BytesIO()
    doc.save(buf)
    return sanitize_docx_bytes(buf.getvalue())
