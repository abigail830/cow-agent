"""Tests for html-ppt bundling."""

from __future__ import annotations

from app.slide.html_ppt import (
    build_html_ppt_dist,
    collect_html_ppt_assets,
    extract_html_ppt_asset_relpaths,
    rewrite_html_ppt_asset_paths,
)


def test_rewrite_html_ppt_asset_paths() -> None:
    html = '<link href="../../assets/base.css"><body data-theme-base="../../assets/themes/">'
    out = rewrite_html_ppt_asset_paths(html)
    assert "./assets/base.css" in out
    assert 'data-theme-base="./assets/themes/' in out


def test_build_html_ppt_dist_includes_referenced_assets_only() -> None:
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<link rel="stylesheet" href="../../assets/base.css">
<link rel="stylesheet" href="../../assets/themes/corporate-clean.css">
<script src="../../assets/runtime.js"></script>
</head>
<body><div class="deck"><section class="slide"><h1>Hi</h1></section></div></body>
</html>"""
    dist = build_html_ppt_dist(html)
    assert "index.html" in dist
    assert "assets/base.css" in dist
    assert "assets/fonts.css" in dist
    assert "assets/runtime.js" in dist
    assert "assets/themes/corporate-clean.css" in dist
    assert not any(path.endswith(".pptx") for path in dist)
    assert "assets/inspire/cover.pptx" not in dist
    assert len([path for path in dist if path.startswith("assets/")]) < 10
    assert b"./assets/base.css" in dist["index.html"]
    assert b"Hi" in dist["index.html"]


def test_build_html_ppt_dist_includes_inspire_image_only() -> None:
    html = """<!DOCTYPE html>
<html><body class="tpl-inspire-brand"><div class="deck"><section class="slide inspire-content">
<img class="inspire-logo" src="../../assets/inspire/logo-white.png"></section></div></body></html>"""
    dist = build_html_ppt_dist(html)
    assert "assets/inspire/logo-white.png" in dist
    assert "assets/inspire/pptstyle.json" not in dist
    assert "assets/inspire/cover.pptx" not in dist
    assert b"./assets/inspire/logo-white.png" in dist["index.html"]


def test_extract_html_ppt_asset_relpaths_includes_fx_modules() -> None:
    html = """<html><body>
<script src="./assets/animations/fx-runtime.js"></script>
<div data-fx="knowledge-graph"></div>
</body></html>"""
    rels = extract_html_ppt_asset_relpaths(html)
    assert "animations/fx-runtime.js" in rels
    assert "animations/fx/_util.js" in rels
    assert "animations/fx/knowledge-graph.js" in rels


def test_collect_html_ppt_assets_skips_pptx_even_if_referenced() -> None:
    html = '<a href="./assets/inspire/cover.pptx">ref</a>'
    dist = collect_html_ppt_assets(html)
    assert "assets/inspire/cover.pptx" not in dist
