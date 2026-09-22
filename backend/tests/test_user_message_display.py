import uuid

from agent_framework import Content, Message

from app.platform.attachments.materialize import (
    build_user_message_with_attachments,
    is_attachment_materialization_text,
    split_user_prompt_text,
)
from app.platform.memory.maf_mapping import maf_message_to_rows


def test_split_user_prompt_text_strips_legacy_attachment_tail() -> None:
    merged = "总结一下这篇的内容\n\n### doc.md (text/markdown, 1 KB)\n```\nbody\n```"
    assert split_user_prompt_text(merged) == "总结一下这篇的内容"


def test_build_user_message_keeps_prompt_and_attachment_separate(monkeypatch) -> None:
    chat_id = uuid.uuid4()
    att_id = uuid.uuid4()
    monkeypatch.setattr(
        "app.platform.attachments.materialize.load_attachment_bytes",
        lambda *_args, **_kwargs: b"# Title\n\nBody",
    )
    message = build_user_message_with_attachments(
        "总结一下这篇的内容",
        [
            {
                "id": att_id,
                "filename": "doc.md",
                "mime_type": "text/markdown",
                "size_bytes": 12,
                "provider": "inline",
                "provider_file_id": f"inline:{att_id}",
            }
        ],
        chat_id=chat_id,
    )
    assert isinstance(message, Message)
    assert len(message.contents) >= 2
    assert message.contents[0].text == "总结一下这篇的内容"
    assert is_attachment_materialization_text(message.contents[1].text)


def test_maf_message_to_rows_user_shows_prompt_and_attachment_chips_only() -> None:
    chat_id = str(uuid.uuid4())
    message = Message(
        role="user",
        contents=[
            Content.from_text("总结一下"),
            Content.from_text("### doc.md (text/markdown, 1 KB)\n```\nsecret\n```"),
        ],
        additional_properties={
            "platform": {
                "attachments": [
                    {
                        "id": "att-1",
                        "filename": "doc.md",
                        "mime_type": "text/markdown",
                        "size_bytes": 12,
                    }
                ]
            }
        },
    )
    rows = maf_message_to_rows(chat_id, message, start_sequence=1)
    assert len(rows) == 1
    assert rows[0]["content"] == "总结一下"
    assert rows[0]["metadata"]["attachments"][0]["filename"] == "doc.md"
