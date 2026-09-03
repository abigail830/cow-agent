"""Bundle html-ppt static decks for chat artifact preview."""

from __future__ import annotations

import re
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
HTML_PPT_SKILL_ROOT = _BACKEND_ROOT / "agents" / "slide-studio" / "skills" / "html-ppt"
HTML_PPT_ASSETS_ROOT = HTML_PPT_SKILL_ROOT / "assets"

_ASSET_PATH_RES = (
    re.compile(r"(?:\.\./)+assets/"),
    re.compile(r'''(data-theme-base=["'])(?:\.\./)+assets/themes/'''),
)


def rewrite_html_ppt_asset_paths(html: str) -> str:
    """Point deck markup at bundled ./assets/ paths for nested preview routes."""
    text = html or ""
    text = _ASSET_PATH_RES[0].sub("./assets/", text)
    text = _ASSET_PATH_RES[1].sub(r"\1./assets/themes/", text)
    return text


def collect_html_ppt_assets() -> dict[str, bytes]:
    """Copy shared html-ppt assets into artifact dist/ tree."""
    if not HTML_PPT_ASSETS_ROOT.is_dir():
        raise FileNotFoundError(f"html-ppt assets not found: {HTML_PPT_ASSETS_ROOT}")

    files: dict[str, bytes] = {}
    for path in HTML_PPT_ASSETS_ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(HTML_PPT_ASSETS_ROOT).as_posix()
        files[f"assets/{rel}"] = path.read_bytes()
    return files


def build_html_ppt_dist(source_html: str) -> dict[str, bytes]:
    """Build preview dist for a html-ppt deck (index.html + bundled assets)."""
    html = rewrite_html_ppt_asset_paths(source_html.strip())
    if not html:
        raise ValueError("HTML source is empty.")
    if "<html" not in html.lower():
        raise ValueError("HTML source must be a complete document with <html>.")

    dist = collect_html_ppt_assets()
    dist["index.html"] = html.encode("utf-8")
    return dist
