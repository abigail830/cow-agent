"""Tests for Slidev dist base rewriting."""

from __future__ import annotations

from pathlib import Path

from app.slide.dist_base import normalize_preview_base, rewrite_slidev_dist_base


def test_normalize_preview_base_adds_trailing_slash() -> None:
    assert normalize_preview_base("/api/v1/preview") == "/api/v1/preview/"


def test_rewrite_slidev_dist_base_patches_router() -> None:
    dist_root = Path("/tmp/slidev-test/dist")
    index_files = list(dist_root.glob("assets/index-*.js"))
    if not index_files:
        return

    raw = index_files[0].read_bytes()
    assert b'./"' in raw
    preview_base = "/api/v1/chats/x/artifacts/slide-y/preview/"
    out = rewrite_slidev_dist_base({index_files[0].name: raw}, preview_base)
    patched = out[index_files[0].name].decode("utf-8")
    assert f'di("{preview_base}")' in patched
    assert f'ma="{preview_base}"' in patched
