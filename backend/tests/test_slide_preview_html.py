"""Tests for Slidev preview HTML helpers."""

from __future__ import annotations

from app.artifacts.preview_html import prepare_slide_preview_html


def test_prepare_slide_preview_html_injects_base_tag() -> None:
    html = b"<!DOCTYPE html><html><head></head><body><div id='app'></div></body></html>"
    out = prepare_slide_preview_html(
        html,
        base_href="/api/v1/chats/x/artifacts/slide-y/preview/",
    ).decode("utf-8")
    assert '<base href="/api/v1/chats/x/artifacts/slide-y/preview/">' in out


def test_prepare_slide_preview_html_injects_router_fix() -> None:
    html = b"<!DOCTYPE html><html><head></head><body><div id='app'></div></body></html>"
    out = prepare_slide_preview_html(
        html,
        base_href="/api/v1/chats/x/artifacts/slide-y/preview/",
    ).decode("utf-8")
    assert "index.html" in out
    assert "history.replaceState" in out


def test_prepare_slide_preview_html_replaces_existing_base_tag() -> None:
    html = b"<!DOCTYPE html><html><head><base href=\"/\"></head><body></body></html>"
    out = prepare_slide_preview_html(html, base_href="/api/v1/chats/x/artifacts/slide-y/preview/").decode(
        "utf-8"
    )
    assert 'href="/api/v1/chats/x/artifacts/slide-y/preview/"' in out
    assert 'href="/"' not in out
