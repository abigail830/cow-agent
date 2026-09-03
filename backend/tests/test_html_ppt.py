"""Tests for html-ppt bundling."""

from __future__ import annotations

from app.slide.html_ppt import build_html_ppt_dist, rewrite_html_ppt_asset_paths


def test_rewrite_html_ppt_asset_paths() -> None:
    html = '<link href="../../assets/base.css"><body data-theme-base="../../assets/themes/">'
    out = rewrite_html_ppt_asset_paths(html)
    assert './assets/base.css' in out
    assert 'data-theme-base="./assets/themes/' in out


def test_build_html_ppt_dist_includes_assets() -> None:
    html = """<!DOCTYPE html>
<html lang="en">
<head>
<link rel="stylesheet" href="../../assets/base.css">
<script src="../../assets/runtime.js"></script>
</head>
<body><section class="slide"><h1>Hi</h1></section></body>
</html>"""
    dist = build_html_ppt_dist(html)
    assert "index.html" in dist
    assert any(path.startswith("assets/") for path in dist)
    assert b"./assets/base.css" in dist["index.html"]
    assert b"Hi" in dist["index.html"]
