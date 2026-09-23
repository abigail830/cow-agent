from __future__ import annotations

import uuid

from app.platform.attachments.materialize import materialize_attachments, should_hydrate_parsed_document
from app.platform.attachments.capabilities import attachment_capabilities
from app.platform.doc_retrieval.context import ChatAttachmentIndexEntry, init_doc_retrieval_context, reset_doc_retrieval_context


def test_should_hydrate_deepseek_pdf_when_parse_ready(monkeypatch):
    caps = attachment_capabilities(model_id="deepseek-flash", provider="deepseek")
    chat_id = uuid.uuid4()
    item = {
        "id": str(uuid.uuid4()),
        "filename": "doc.pdf",
        "mime_type": "application/pdf",
        "parse_status": "ready",
    }
    monkeypatch.setattr(
        "app.platform.attachments.materialize.parsed_artifact_exists",
        lambda *_args, **_kwargs: True,
    )
    assert should_hydrate_parsed_document(item, caps, chat_id=chat_id) is True


def test_should_not_hydrate_claude_pdf_file_id():
    caps = attachment_capabilities(model_id="claude-sonnet-4-6", provider="azure_anthropic")
    item = {
        "id": str(uuid.uuid4()),
        "filename": "doc.pdf",
        "mime_type": "application/pdf",
        "parse_status": "ready",
    }
    assert should_hydrate_parsed_document(item, caps) is False


def test_materialize_hydrate_emits_manifest_not_raster(monkeypatch):
    reset_doc_retrieval_context()
    chat_id = uuid.uuid4()
    att_id = str(uuid.uuid4())
    init_doc_retrieval_context(
        chat_id=chat_id,
        library={
            att_id: ChatAttachmentIndexEntry(
                attachment_id=att_id,
                filename="brief.pdf",
                mime_type="application/pdf",
                kind="pdf",
                parse_status="ready",
                page_count=5,
                figure_count=1,
            )
        },
    )
    item = {
        "id": att_id,
        "filename": "brief.pdf",
        "mime_type": "application/pdf",
        "parse_status": "ready",
        "size_bytes": 1000,
    }

    monkeypatch.setattr(
        "app.platform.attachments.materialize.parsed_artifact_exists",
        lambda _chat_id, _att_id, key: key == "content_md",
    )
    parts = materialize_attachments(
        [item],
        chat_id=chat_id,
        model_id="deepseek-flash",
        provider="deepseek",
    )
    assert len(parts) == 1
    assert parts[0].type == "text"
    text = parts[0].text or ""
    assert "attachment_grep" in text
    assert "brief.pdf" in text
    assert "raster" not in text.lower()
    reset_doc_retrieval_context()
