"""Smoke tests for Content Studio artifact publishing."""

from __future__ import annotations

import uuid

from app.shared.artifacts.content_studio_builder import build_content_studio_artifact_spec


def test_build_content_studio_html_artifact_spec(monkeypatch) -> None:
    chat_id = uuid.uuid4()
    html = b"<!DOCTYPE html><html><body><h1>Deck</h1></body></html>"
    saved: dict[str, object] = {}

    def _fake_save_slide_deck(chat_id_arg, artifact_id, **kwargs) -> None:
        saved["chat_id"] = chat_id_arg
        saved["artifact_id"] = artifact_id
        saved.update(kwargs)

    monkeypatch.setattr(
        "app.shared.artifacts.content_studio_builder.save_slide_deck",
        _fake_save_slide_deck,
    )

    spec = build_content_studio_artifact_spec(
        sandbox_path="/home/user/content-studio/deck.html",
        file_bytes=html,
        title="Q1 Review",
        chat_id=chat_id,
    )

    assert spec.kind == "slide_deck"
    assert spec.format == "html"
    assert spec.filename == "deck.html"
    assert spec.download_url == f"/api/v1/chats/{chat_id}/artifacts/{spec.artifact_id}"
    assert spec.preview_url == f"/api/v1/chats/{chat_id}/artifacts/{spec.artifact_id}/preview"
    assert saved["deck_format"] == "html"
    assert saved["dist_files"] == {"index.html": html}
