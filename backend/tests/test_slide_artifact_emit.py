"""Tests for slide artifact SSE emit."""

from __future__ import annotations

import uuid

from app.artifacts.context import init_run_artifact_state, reset_run_artifact_state
from app.artifacts.spec import ArtifactSpec
from app.services.chat_run import _StreamTurnAccumulator, _emit_pending_artifact_events


def test_emit_pending_slide_artifact_events() -> None:
    reset_run_artifact_state()
    chat_id = uuid.uuid4()
    ctx = init_run_artifact_state(chat_id=chat_id)
    spec = ArtifactSpec(
        kind="slide_deck",
        title="Quarterly Review",
        format="slidev",
        content="",
        filename="review.md",
        artifact_id="slide-abc123",
        preview_url=f"/api/v1/chats/{chat_id}/artifacts/slide-abc123/preview/",
        source="# Title",
    )
    ctx.queue_artifact(spec)

    accumulator = _StreamTurnAccumulator()
    events = _emit_pending_artifact_events(chat_id, accumulator)

    assert len(events) == 1
    assert events[0]["event"] == "artifact"
    payload = events[0]["data"]["spec"]
    assert payload["kind"] == "slide_deck"
    assert payload["preview_url"] is not None
    reset_run_artifact_state()


def test_slide_artifact_spec_with_md_download() -> None:
    chat_id = uuid.uuid4()
    spec = ArtifactSpec(
        kind="slide_deck",
        title="Deck",
        format="slidev",
        content="# Slide",
        filename="deck.md",
        artifact_id="slide-xyz",
        download_url=f"/api/v1/chats/{chat_id}/artifacts/slide-xyz",
        pdf_download_url=f"/api/v1/chats/{chat_id}/artifacts/slide-xyz?format=pdf",
        pdf_filename="deck.pdf",
        preview_url=f"/api/v1/chats/{chat_id}/artifacts/slide-xyz/preview/",
    )
    assert spec.download_url.endswith("/slide-xyz")
    assert spec.pdf_download_url is not None
