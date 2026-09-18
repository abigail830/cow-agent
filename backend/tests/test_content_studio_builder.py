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


def test_build_content_studio_markdown_artifact_spec(monkeypatch) -> None:
    chat_id = uuid.uuid4()
    md = b"# Backlog\n\n- item one\n"
    saved: dict[str, object] = {}

    def _fake_save_content_file(chat_id_arg, artifact_id, **kwargs) -> None:
        saved["chat_id"] = chat_id_arg
        saved["artifact_id"] = artifact_id
        saved.update(kwargs)

    monkeypatch.setattr(
        "app.shared.artifacts.content_studio_builder.save_content_file",
        _fake_save_content_file,
    )

    spec = build_content_studio_artifact_spec(
        sandbox_path="/home/user/content-studio/notes.md",
        file_bytes=md,
        title="OMNI backlog",
        chat_id=chat_id,
    )

    assert spec.kind == "content_document"
    assert spec.format == "markdown"
    assert spec.filename == "notes.md"
    assert spec.content == "# Backlog\n\n- item one\n"
    assert spec.preview_truncated is False
    assert spec.download_url == f"/api/v1/chats/{chat_id}/artifacts/{spec.artifact_id}"
    assert saved["file_format"] == "markdown"
    assert saved["filename"] == "notes.md"
