from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.platform.attachments.metadata import attachment_metadata


def test_attachment_metadata_hub_item_uses_chat_context():
    hub_id = uuid4()
    chat_id = uuid4()
    item = SimpleNamespace(
        id=hub_id,
        user_id=uuid4(),
        folder_id=uuid4(),
        filename="doc.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        provider="inline",
        provider_file_id=str(hub_id),
        parse_status="ready",
        parse_pipeline_id=None,
        parse_job_id=None,
        parse_error_message=None,
        parse_stage_snapshot=None,
    )
    meta = attachment_metadata(item, chat_id=chat_id)
    assert meta["chat_id"] == str(chat_id)
    assert meta["source"] == "hub_item"
    assert meta["provider"] == "hub"
    assert meta["user_id"] == str(item.user_id)
