import uuid

import pytest

from app.platform.attachments.materialization.snapshot import (
    enrich_metadata_with_extracted_snapshots,
    snapshot_from_extracted,
)
from app.platform.attachments.unify_lite.types import ExtractedAttachment


class _Attachment:
    def __init__(self, attachment_id: uuid.UUID, *, provider_file_id: str) -> None:
        self.id = attachment_id
        self.provider_file_id = provider_file_id
        self.filename = "report.docx"
        self.mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        self.size_bytes = 100
        self.provider = "unify_lite"


def test_snapshot_from_extracted_includes_text() -> None:
    item = ExtractedAttachment(
        attachment_id=uuid.uuid4(),
        filename="notes.txt",
        mime_type="text/plain",
        content="hello snapshot",
        char_count=14,
    )
    snapshot = snapshot_from_extracted(item, content_hash="sha256:abc")
    assert snapshot["text"] == "hello snapshot"
    assert snapshot["content_hash"] == "sha256:abc"
    assert snapshot["char_count"] == 14
    assert snapshot["extracted_at"]


def test_enrich_metadata_with_extracted_snapshots(monkeypatch) -> None:
    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    att = _Attachment(attachment_id, provider_file_id=f"inline:{attachment_id}")
    extracted = [
        ExtractedAttachment(
            attachment_id=attachment_id,
            filename="report.docx",
            mime_type=att.mime_type,
            content="Quarterly revenue grew 12%.",
            char_count=27,
        )
    ]
    metadata = {
        "attachment_mode": "unify_lite",
        "attachments": [
            {
                "id": str(attachment_id),
                "filename": att.filename,
                "mime_type": att.mime_type,
                "size_bytes": att.size_bytes,
                "provider": att.provider,
                "provider_file_id": att.provider_file_id,
            }
        ],
    }

    monkeypatch.setattr(
        "app.platform.attachments.materialization.snapshot.compute_attachment_content_hash",
        lambda _chat_id, _provider_file_id: "sha256:deadbeef",
    )

    enriched = enrich_metadata_with_extracted_snapshots(
        metadata,
        extracted,
        chat_id=chat_id,
        attachments=[att],
    )
    snapshot = enriched["attachments"][0]["extracted_snapshot"]
    assert snapshot["text"] == "Quarterly revenue grew 12%."
    assert snapshot["content_hash"] == "sha256:deadbeef"
