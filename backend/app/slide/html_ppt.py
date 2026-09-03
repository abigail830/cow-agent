"""Bundle html-ppt static decks for chat artifact preview."""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

from app.slide.html_ppt_normalize import normalize_html_ppt_source

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
HTML_PPT_SKILL_ROOT = _BACKEND_ROOT / "agents" / "slide-studio" / "skills" / "html-ppt"
HTML_PPT_ASSETS_ROOT = HTML_PPT_SKILL_ROOT / "assets"

_SKIPPED_ASSET_SUFFIXES = {".pptx"}

_CORE_ASSETS = (
    "base.css",
    "fonts.css",
    "runtime.js",
)

_ASSET_PATH_RES = (
    re.compile(r"(?:\.\./)+assets/"),
    re.compile(r'''(data-theme-base=["'])(?:\.\./)+assets/themes/'''),
)

_ASSET_REF_RE = re.compile(
    r"""\.?/?assets/([^"'<>)\s]+)""",
    re.IGNORECASE,
)

_INSPIRE_SCOPED_ASSET = "inspire-deck-scoped.css"
_ASC_SCOPED_ASSET = "asc-deck-scoped.css"
_INSPIRE_SCOPED_CSS = HTML_PPT_ASSETS_ROOT / _INSPIRE_SCOPED_ASSET
_ASC_SCOPED_CSS = HTML_PPT_ASSETS_ROOT / _ASC_SCOPED_ASSET
_INSPIRE_SCOPED_CSS_FALLBACK = (
    HTML_PPT_SKILL_ROOT / "templates/full-decks/inspire-brand/style.css"
)

_SCOPED_ASSET_PATHS: dict[str, Path] = {
    _INSPIRE_SCOPED_ASSET: _INSPIRE_SCOPED_CSS,
    _ASC_SCOPED_ASSET: _ASC_SCOPED_CSS,
}

_FX_NAME_RE = re.compile(r"""data-fx=["']([^"']+)["']""", re.IGNORECASE)


def rewrite_html_ppt_asset_paths(html: str) -> str:
    """Point deck markup at bundled ./assets/ paths for nested preview routes."""
    text = html or ""
    text = _ASSET_PATH_RES[0].sub("./assets/", text)
    text = _ASSET_PATH_RES[1].sub(r"\1./assets/themes/", text)
    return text


def _normalize_asset_relpath(raw: str) -> str | None:
    rel = unquote((raw or "").strip()).lstrip("/").replace("\\", "/")
    if not rel or ".." in rel.split("/"):
        return None
    if Path(rel).suffix.lower() in _SKIPPED_ASSET_SUFFIXES:
        return None
    return rel


def extract_html_ppt_asset_relpaths(html: str) -> set[str]:
    """Collect asset paths referenced by deck HTML (after path rewrite)."""
    rels: set[str] = set()
    for match in _ASSET_REF_RE.finditer(html or ""):
        rel = _normalize_asset_relpath(match.group(1))
        if rel:
            rels.add(rel)

    if re.search(r"""class=["'][^"']*\bdeck\b""", html or "", re.IGNORECASE) or re.search(
        r"""class=["'][^"']*\bslide\b""",
        html or "",
        re.IGNORECASE,
    ):
        rels.update(_CORE_ASSETS)

    if re.search(r"data-anim|animations\.css", html or "", re.IGNORECASE):
        rels.add("animations/animations.css")

    if any("fx-runtime.js" in rel for rel in rels) or "data-fx" in (html or ""):
        rels.add("animations/fx-runtime.js")
        rels.add("animations/fx/_util.js")
        for fx_name in _FX_NAME_RE.findall(html or ""):
            name = fx_name.strip()
            if name and re.fullmatch(r"[a-z0-9-]+", name):
                rels.add(f"animations/fx/{name}.js")

    for scoped_asset in _SCOPED_ASSET_PATHS:
        if f"assets/{scoped_asset}" in html or scoped_asset in html:
            rels.add(scoped_asset)

    return rels


def collect_html_ppt_assets(html: str) -> dict[str, bytes]:
    """Copy only assets referenced by the deck (skip pptx and other unreferenced files)."""
    if not HTML_PPT_ASSETS_ROOT.is_dir():
        raise FileNotFoundError(f"html-ppt assets not found: {HTML_PPT_ASSETS_ROOT}")

    files: dict[str, bytes] = {}
    for rel in sorted(extract_html_ppt_asset_relpaths(html)):
        if rel in _SCOPED_ASSET_PATHS:
            scoped_path = _SCOPED_ASSET_PATHS[rel]
            if rel == _INSPIRE_SCOPED_ASSET and not scoped_path.is_file():
                scoped_path = _INSPIRE_SCOPED_CSS_FALLBACK
            if scoped_path.is_file():
                files[f"assets/{rel}"] = scoped_path.read_bytes()
            continue
        path = (HTML_PPT_ASSETS_ROOT / rel).resolve()
        if not path.is_file():
            continue
        if not path.is_relative_to(HTML_PPT_ASSETS_ROOT.resolve()):
            continue
        files[f"assets/{rel}"] = path.read_bytes()
    return files


def build_html_ppt_dist(source_html: str) -> dict[str, bytes]:
    """Build preview dist for a html-ppt deck (index.html + bundled assets)."""
    html = normalize_html_ppt_source(source_html.strip())
    html = rewrite_html_ppt_asset_paths(html)
    if not html:
        raise ValueError("HTML source is empty.")
    if "<html" not in html.lower():
        raise ValueError("HTML source must be a complete document with <html>.")

    dist = collect_html_ppt_assets(html)
    dist["index.html"] = html.encode("utf-8")
    return dist
