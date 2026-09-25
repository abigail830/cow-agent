"""Office markdown quality gate — runtime heuristics, no ground truth."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from parse_pipeline.quality.docx_probe import DocxProbe

try:
    from ftfy.badness import badness as ftfy_badness
except ImportError:  # pragma: no cover

    def ftfy_badness(text: str) -> int:
        return 0


class GateGrade(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


class GateDecision(StrEnum):
    ACCEPT = "accept"
    FALLBACK = "fallback"


_GLYPH_RE = re.compile(r"GLYPH<[0-9A-Fa-f]+>")
_SLASH_G_RE = re.compile(r"(?:/G\d+){2,}")
_CID_RE = re.compile(r"\(cid:\d+\)", re.I)
_FRAG_WORD_RE = re.compile(r"\b[A-Za-z](?:/[a-z]{1,3}\.[a-z]{1,3}){2,}\b")

_PUA_RANGES = (range(0xE000, 0xF900),)


def _is_garbled_char(ch: str) -> bool:
    if not ch or ch.isspace():
        return False
    o = ord(ch)
    if ch == "\ufffd":
        return True
    if o in _PUA_RANGES:
        return True
    if 0xF0000 <= o <= 0xFFFFD or 0x100000 <= o <= 0x10FFFD:
        return True
    return False


def rate_text_quality(text: str) -> float:
    if not text.strip():
        return 0.0
    if _GLYPH_RE.search(text) or _SLASH_G_RE.search(text) or _CID_RE.search(text):
        return 0.0

    non_space = [c for c in text if not c.isspace()]
    if not non_space:
        return 0.0

    garbled = sum(1 for c in non_space if _is_garbled_char(c))
    ratio = garbled / len(non_space)
    if ratio >= 0.05:
        return max(0.0, 1.0 - ratio * 2)

    frag_hits = len(_FRAG_WORD_RE.findall(text))
    penalty = 0.1 * frag_hits if frag_hits >= 3 else 0.0
    mojibake_penalty = min(0.5, ftfy_badness(text) * 0.05)
    return max(0.0, 1.0 - penalty - mojibake_penalty)


def garbled_ratio(text: str) -> float:
    non_space = [c for c in text if not c.isspace()]
    if not non_space:
        return 0.0
    return sum(1 for c in non_space if _is_garbled_char(c)) / len(non_space)


_TRUNCATED_DATA_URI = re.compile(r"data:image/[^;]+;base64\.\.\.")
_HEADING_RE = re.compile(r"^#{1,6}\s+\S", re.M)
_TABLE_PIPE_RE = re.compile(r"^\s*\|.*\|\s*$", re.M)
_HTML_TABLE_RE = re.compile(r"<table\b", re.I)
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\([^)]+\)")


@dataclass
class MarkdownSignals:
    chars: int
    printable_chars: int
    lines: int
    headings: int
    table_markers: int
    images: int
    truncated_image_placeholders: int
    list_lines: int

    @classmethod
    def from_text(cls, text: str) -> MarkdownSignals:
        lines = text.splitlines()
        table_markers = len(_TABLE_PIPE_RE.findall(text)) + len(_HTML_TABLE_RE.findall(text))
        return cls(
            chars=len(text),
            printable_chars=sum(1 for c in text if c.isprintable() or c in "\n\t"),
            lines=len(lines),
            headings=len(_HEADING_RE.findall(text)),
            table_markers=table_markers,
            images=len(_IMAGE_RE.findall(text)),
            truncated_image_placeholders=len(_TRUNCATED_DATA_URI.findall(text)),
            list_lines=sum(1 for ln in lines if re.match(r"^(\*|-|\d+\.)\s+\S", ln)),
        )


@dataclass
class GateCheck:
    code: str
    passed: bool
    detail: str
    severity: str = "error"


@dataclass
class GateResult:
    decision: GateDecision
    grade: GateGrade
    parse_score: float
    checks: list[GateCheck] = field(default_factory=list)
    signals: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.decision == GateDecision.ACCEPT

    def fallback_reasons(self) -> list[str]:
        return [c.code for c in self.checks if not c.passed and c.severity == "error"]


def _grade_from_score(score: float) -> GateGrade:
    if score >= 0.9:
        return GateGrade.EXCELLENT
    if score >= 0.8:
        return GateGrade.GOOD
    if score >= 0.5:
        return GateGrade.FAIR
    return GateGrade.POOR


def evaluate_office_markdown(
    content: str,
    *,
    probe: DocxProbe,
    converter_ok: bool = True,
    converter_error: str | None = None,
) -> GateResult:
    checks: list[GateCheck] = []
    md = MarkdownSignals.from_text(content)
    text_q = rate_text_quality(content)

    signals: dict[str, Any] = {
        "probe": asdict(probe),
        "markdown": asdict(md),
        "text_quality": round(text_q, 4),
        "garbled_ratio": round(garbled_ratio(content), 4),
    }

    def add(code: str, passed: bool, detail: str, *, severity: str = "error") -> None:
        checks.append(GateCheck(code=code, passed=passed, detail=detail, severity=severity))

    add("converter_ok", converter_ok, converter_error or "converter succeeded")
    add("non_empty", bool(content.strip()), f"printable output chars={md.printable_chars}")
    add(
        "no_truncated_images",
        md.truncated_image_placeholders == 0,
        f"truncated data-uri placeholders={md.truncated_image_placeholders}",
    )
    add("not_legacy_doc", not probe.has_legacy_doc, "legacy .doc requires non-local path")

    min_yield = 0.08 if probe.is_small else 0.15
    if probe.text_chars > 0:
        yield_ratio = md.printable_chars / probe.text_chars
        signals["yield_ratio"] = round(yield_ratio, 4)
        add(
            "text_yield",
            yield_ratio >= min_yield,
            f"yield={yield_ratio:.3f} min={min_yield} (probe text_chars={probe.text_chars})",
        )
    else:
        add("text_yield", md.printable_chars > 32, "no probed text; require minimal output", severity="warn")

    add("text_quality", text_q >= 0.85, f"parse_score={text_q:.3f} (docling-style)")
    add(
        "garbled_ratio",
        garbled_ratio(content) < 0.05,
        f"garbled_ratio={garbled_ratio(content):.3f} threshold=0.05",
    )

    if probe.image_count >= 10:
        retention = md.images / probe.image_count
        signals["image_retention_ratio"] = round(retention, 4)
        add(
            "image_retention",
            retention >= 0.5,
            f"probe images={probe.image_count} md images={md.images} ratio={retention:.3f}",
        )

    if not probe.is_small:
        if probe.table_count >= 2:
            add(
                "tables_preserved",
                md.table_markers >= 2,
                f"probe tables={probe.table_count} output table markers={md.table_markers}",
            )
        if probe.heading_style_count >= 3 and probe.is_large:
            has_structure = md.headings >= 2 or md.list_lines >= 5
            add(
                "structure_preserved",
                has_structure,
                (
                    f"probe heading styles={probe.heading_style_count} "
                    f"md headings={md.headings} list_lines={md.list_lines}"
                ),
            )
        if probe.image_count >= 1:
            add(
                "images_present_or_materializable",
                md.images >= 1 or md.truncated_image_placeholders == 0,
                f"probe images={probe.image_count} md images={md.images}",
                severity="warn",
            )

    failed_errors = [c for c in checks if not c.passed and c.severity == "error"]
    decision = GateDecision.ACCEPT if not failed_errors else GateDecision.FALLBACK
    grade = _grade_from_score(text_q if content.strip() else 0.0)

    return GateResult(
        decision=decision,
        grade=grade,
        parse_score=text_q,
        checks=checks,
        signals=signals,
    )
