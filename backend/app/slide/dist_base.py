"""Rewrite Slidev dist bundles so Vue Router uses the nested preview base path."""

from __future__ import annotations

import re

_HISTORY_BASE_RE = re.compile(r'history:(\w+)\("\./"\)')
_MODULE_BASE_RE = re.compile(r'ma="\./"')


def normalize_preview_base(base_href: str) -> str:
    trimmed = (base_href or "").strip()
    if not trimmed:
        raise ValueError("preview base href is required")
    return trimmed if trimmed.endswith("/") else f"{trimmed}/"


def rewrite_slidev_dist_base(dist_files: dict[str, bytes], preview_base: str) -> dict[str, bytes]:
    """Patch Slidev SPA bundles built with ``--base ./`` for nested API preview routes."""
    base = normalize_preview_base(preview_base)
    if base == "./":
        return dist_files

    out: dict[str, bytes] = {}
    for path, data in dist_files.items():
        if not path.endswith(".js"):
            out[path] = data
            continue
        text = data.decode("utf-8", errors="surrogateescape")
        if './"' not in text and "('./" not in text:
            out[path] = data
            continue
        patched = _HISTORY_BASE_RE.sub(rf'history:\1("{base}")', text)
        patched = _MODULE_BASE_RE.sub(f'ma="{base}"', patched)
        out[path] = patched.encode("utf-8", errors="surrogateescape")
    return out
