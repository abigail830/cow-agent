"""Helpers for serving Slidev SPA previews through nested API routes."""

from __future__ import annotations

import re

_BASE_TAG_RE = re.compile(r"<base\b[^>]*>", re.IGNORECASE)
_ROUTER_FIX_SCRIPT = (
    "<script>"
    "(function(){"
    "var p=location.pathname;"
    "if (p.endsWith('/index.html')) {"
    "history.replaceState(null,'',p.replace(/\\/index\\.html$/,''));"
    "return;"
    "}"
    "var b=document.querySelector('base');"
    "if(!b) return;"
    "var base=b.getAttribute('href')||'';"
    "if(!base) return;"
    "var norm=base.endsWith('/')?base:base+'/';"
    "if(p===norm||p+'/'===norm){return;}"
    "if(p.startsWith(norm)){"
    "var rest=p.slice(norm.length);"
    "if(rest&&rest!=='/'){history.replaceState(null,'',norm+(rest.startsWith('/')?rest.slice(1):rest));}"
    "}"
    "})();"
    "</script>"
)


def _inject_preview_head(text: str, *, base_href: str, include_router_fix: bool) -> str:
    normalized_base = base_href if base_href.endswith("/") else f"{base_href}/"
    base_tag = f'<base href="{normalized_base}">'
    head_injection = base_tag + (_ROUTER_FIX_SCRIPT if include_router_fix else "")

    if _BASE_TAG_RE.search(text):
        text = _BASE_TAG_RE.sub(base_tag, text, count=1)
        if include_router_fix and _ROUTER_FIX_SCRIPT not in text:
            text = text.replace(base_tag, head_injection, 1)
    elif "<head>" in text:
        text = text.replace("<head>", f"<head>{head_injection}", 1)
    elif "<head " in text:
        text = re.sub(r"(<head\b[^>]*>)", rf"\1{head_injection}", text, count=1, flags=re.IGNORECASE)
    else:
        text = f"<!DOCTYPE html><html><head>{head_injection}</head><body>{text}</body></html>"

    return text


def prepare_slide_preview_html(html: bytes, *, base_href: str) -> bytes:
    """Ensure relative Slidev assets resolve under the preview route."""
    text = html.decode("utf-8", errors="replace")
    text = _inject_preview_head(text, base_href=base_href, include_router_fix=True)
    return text.encode("utf-8")


def prepare_html_ppt_preview_html(html: bytes, *, base_href: str) -> bytes:
    """Inject preview base for html-ppt decks (no Slidev router rewrite)."""
    text = html.decode("utf-8", errors="replace")
    text = _inject_preview_head(text, base_href=base_href, include_router_fix=False)
    return text.encode("utf-8")


SLIDE_PREVIEW_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' blob: https://unpkg.com; "
    "script-src-elem 'self' 'unsafe-inline' 'unsafe-eval' blob: https://unpkg.com; "
    "style-src 'self' 'unsafe-inline' https:; "
    "img-src * data: blob:; "
    "font-src 'self' data: https:; "
    "connect-src 'self' https: blob:; "
    "worker-src 'self' blob:; "
    "media-src * data: blob:; "
    "frame-ancestors 'self';"
)
