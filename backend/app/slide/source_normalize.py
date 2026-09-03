"""Normalize Slidev Markdown before build."""

from __future__ import annotations

import re

_HTML_TAG_LINE = re.compile(
    r"^\s+("
    r"</?(?:div|ul|ol|li|span|p|section|header|footer|nav|article|style|script|"
    r"h[1-6]|table|tr|td|th|thead|tbody|a|button|input|img|svg|path|g|text|"
    r"i|strong|em|br|hr|main|aside|label|form|template|slot|component)[\s>/]"
    r"|<!--"
    r")",
    re.IGNORECASE,
)

_LAYOUT_HTML_FENCE = re.compile(
    r"```(?:html|HTML)\s*\n(.*?)\n```",
    re.DOTALL,
)

_LAYOUT_HTML_MARKERS = re.compile(
    r"<(?:div|ul|ol|section|style|table|grid|card)\b",
    re.IGNORECASE,
)


def normalize_slidev_source(source: str) -> str:
    """Fix common LLM patterns that make HTML render as literal text in Slidev."""
    text = (source or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return text

    text = _unwrap_layout_html_fences(text)
    lines = text.split("\n")
    out: list[str] = []
    in_fence = False

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        if _HTML_TAG_LINE.match(line):
            out.append(line.lstrip())
            continue
        out.append(line)

    return "\n".join(out)


def _unwrap_layout_html_fences(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        body = match.group(1)
        if _LAYOUT_HTML_MARKERS.search(body):
            return body.strip()
        return match.group(0)

    return _LAYOUT_HTML_FENCE.sub(repl, text)
