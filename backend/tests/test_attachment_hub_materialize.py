from __future__ import annotations

import uuid

import pytest

from app.platform.attachments.capabilities import attachment_capabilities
from app.platform.attachments.materialize import materialize_attachments, should_hydrate_parsed_document
from app.platform.attachments.source import (
    HubDocumentMaterializeError,
    attachment_materialize_source,
    raise_if_hub_document_blocked_from_inline,
)


def test_attachment_materialize_source_from_metadata_dict():
    item = {
        "id": str(uuid.uuid4()),
        "chat_id": str(uuid.uuid4()),
        "source": "hub_item",
        "filename": "a.pdf",
    }
    assert attachment_materialize_source(item) == "hub_item"


def test_should_hydrate_hub_pdf_even_when_claude_pdf_file_id(monkeypatch):
    caps = attachment_capabilities(model_id="claude-sonnet-4-6", provider="azure_anthropic")
    user_id = uuid.uuid4()
    item = {
        "id": str(uuid.uuid4()),
        "user_id": str(user_id),
        "source": "hub_item",
        "filename": "doc.pdf",
        "mime_type": "application/pdf",
        "parse_status": "ready",
    }
    monkeypatch.setattr(
        "app.platform.attachments.source.parsed_artifact_exists_scoped",
        lambda *_args, **_kwargs: True,
    )
    assert should_hydrate_parsed_document(item, caps, chat_id=uuid.uuid4()) is True


def test_should_not_hydrate_chat_pdf_for_claude_file_id_without_content_md():
    caps = attachment_capabilities(model_id="claude-sonnet-4-6", provider="azure_anthropic")
    item = {
        "id": str(uuid.uuid4()),
        "filename": "doc.pdf",
        "mime_type": "application/pdf",
        "parse_status": "ready",
    }
    assert should_hydrate_parsed_document(item, caps) is False


def test_raise_if_hub_not_parsed_yet():
    item = {
        "id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "source": "hub_item",
        "filename": "slides.pptx",
        "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "parse_status": "running",
    }
    with pytest.raises(HubDocumentMaterializeError, match="not parsed yet"):
        raise_if_hub_document_blocked_from_inline(item)


def test_hub_pdf_never_binary_inline_when_hydrate_unavailable(monkeypatch):
    chat_id = uuid.uuid4()
    item = {
        "id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "source": "hub_item",
        "filename": "deck.pdf",
        "mime_type": "application/pdf",
        "parse_status": "pending",
    }

    def fail_load(*_args, **_kwargs):
        raise AssertionError("must not load hub original bytes for inline")

    monkeypatch.setattr(
        "app.platform.attachments.materialize.load_attachment_bytes",
        fail_load,
    )
    with pytest.raises(HubDocumentMaterializeError, match="not parsed yet"):
        materialize_attachments(
            [item],
            chat_id=chat_id,
            model_id="qwen3.7-plus",
            provider="dashscope",
        )


def test_should_hydrate_hub_pptx_when_parse_ready(monkeypatch):
    caps = attachment_capabilities(model_id="qwen3.7-plus", provider="dashscope")
    item = {
        "id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "source": "hub_item",
        "filename": "slides.pptx",
        "mime_type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "parse_status": "ready",
    }
    monkeypatch.setattr(
        "app.platform.attachments.source.parsed_artifact_exists_scoped",
        lambda *_args, **_kwargs: True,
    )
    assert should_hydrate_parsed_document(item, caps, chat_id=uuid.uuid4()) is True


def test_raise_if_hub_ready_but_missing_parsed_md(monkeypatch):
    item = {
        "id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "source": "hub_item",
        "filename": "doc.pdf",
        "mime_type": "application/pdf",
        "parse_status": "ready",
    }
    monkeypatch.setattr(
        "app.platform.attachments.source.parsed_artifact_exists_scoped",
        lambda *_args, **_kwargs: False,
    )
    with pytest.raises(HubDocumentMaterializeError, match="parsed markdown is missing"):
        raise_if_hub_document_blocked_from_inline(item)
