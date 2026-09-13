import uuid

import pytest

from app.platform.memory.maf_mapping import to_maf_messages


CHAT_ID = "11111111-1111-1111-1111-111111111111"
ATTACHMENT_ID = "22222222-2222-2222-2222-222222222222"


def _lite_doc_row(*, content: str, sequence: int) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "chat_id": CHAT_ID,
        "role": "user",
        "message_type": "text",
        "content": content,
        "sequence": sequence,
        "metadata": {
            "attachment_mode": "unify_lite",
            "attachments": [
                {
                    "id": ATTACHMENT_ID,
                    "filename": "report.docx",
                    "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "size_bytes": 512,
                    "provider": "unify_lite",
                    "provider_file_id": f"inline:{ATTACHMENT_ID}",
                    "extracted_snapshot": {
                        "content_hash": "sha256:abc123",
                        "text": "Revenue increased 12% year over year.",
                        "truncated": False,
                        "char_count": 38,
                        "extracted_at": "2026-01-01T00:00:00+00:00",
                    },
                }
            ],
        },
    }


def test_to_maf_messages_lite_doc_uses_snapshot_not_raw_bytes(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.platform.attachments.native.maf_content.load_inline_attachment",
        lambda *_args, **_kwargs: pytest.fail("must not load raw doc bytes on replay"),
    )

    rows = [_lite_doc_row(content="Summarize @report.docx", sequence=1)]
    messages = to_maf_messages(rows)

    assert len(messages) == 1
    contents = messages[0].contents
    assert len(contents) == 2
    assert contents[0].type == "text"
    assert contents[0].text == "Summarize @report.docx"
    assert contents[1].type == "text"
    assert "Revenue increased 12%" in (contents[1].text or "")
    assert all(getattr(c, "type", None) != "data" for c in contents)


def test_to_maf_messages_lite_doc_replay_text_matches_snapshot() -> None:
    rows = [_lite_doc_row(content="What were the numbers?", sequence=2)]
    messages = to_maf_messages(rows)
    attachment_text = messages[0].contents[1].text or ""
    assert "report.docx" in attachment_text
    assert "Revenue increased 12%" in attachment_text
