"""Tests for slide artifact storage and sandbox providers."""

from __future__ import annotations

import uuid

from app.artifacts.context import get_run_artifact_state, init_run_artifact_state, reset_run_artifact_state
from app.artifacts.spec import ArtifactSpec
from app.artifacts.storage import (
    chat_artifact_exists,
    load_chat_artifact_payload,
    load_slide_preview_payload,
    new_chat_artifact_id,
    save_slide_deck,
)
from app.sandbox.providers.local import LocalSandboxProvider
from app.slide.renderer import SlideRenderer


def test_run_artifact_state_queue_dedupes() -> None:
    reset_run_artifact_state()
    ctx = init_run_artifact_state(chat_id=uuid.uuid4())
    spec = ArtifactSpec(
        kind="slide_deck",
        title="Demo",
        format="slidev",
        content="# Hi",
        filename="demo.md",
        artifact_id="slide-test123",
    )
    assert ctx.queue_artifact(spec) is True
    assert ctx.queue_artifact(spec) is False
    drained = ctx.drain_pending_artifacts()
    assert len(drained) == 1
    reset_run_artifact_state()
    assert get_run_artifact_state() is None


def test_save_slide_deck_local_and_preview(monkeypatch) -> None:
    monkeypatch.setenv("ARTIFACT_STORAGE", "local")
    from app.config import get_settings

    get_settings.cache_clear()

    chat_id = uuid.uuid4()
    artifact_id = new_chat_artifact_id()
    save_slide_deck(
        chat_id,
        artifact_id,
        source_md="---\ntitle: Test\n---\n\n# Hello",
        filename="hello.md",
        dist_files={
            "index.html": b"<html><body>deck</body></html>",
            "assets/app.js": b"console.log('hi')",
        },
        pdf_bytes=b"%PDF-1.4",
    )

    assert chat_artifact_exists(chat_id, artifact_id)
    md = load_chat_artifact_payload(chat_id, artifact_id)
    assert md is not None
    assert b"Hello" in md.data

    html = load_slide_preview_payload(chat_id, artifact_id, "index.html")
    assert html is not None
    assert b"<html>" in html.data

    html_from_root = load_slide_preview_payload(chat_id, artifact_id, "")
    assert html_from_root is not None
    assert html_from_root.data == html.data

    pdf = load_chat_artifact_payload(chat_id, artifact_id, variant="pdf")
    assert pdf is not None
    assert pdf.data.startswith(b"%PDF")

    get_settings.cache_clear()


def test_local_sandbox_skips_build() -> None:
    provider = LocalSandboxProvider()
    result = provider.build_slidev(slides_md="---\ntitle: X\n---\n\n# Slide")
    assert result.error is None
    assert result.dist_files == {}


def test_slide_renderer_empty_source(monkeypatch) -> None:
    monkeypatch.setenv("SANDBOX_PROVIDER", "local")
    from app.config import get_settings

    get_settings.cache_clear()
    out = SlideRenderer().build("")
    assert out.error == "Slidev source is empty."
    get_settings.cache_clear()
