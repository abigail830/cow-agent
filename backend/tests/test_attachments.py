from agent_framework import Content, Message

from app.memory.maf_mapping import to_maf_messages
from app.platform.user_message_input import build_user_run_input


class _Attachment:
    def __init__(self) -> None:
        self.id = "att-1"
        self.provider_file_id = "file_abc123"
        self.mime_type = "application/pdf"
        self.filename = "report.pdf"
        self.size_bytes = 100
        self.provider = "azure_anthropic"


def test_to_maf_messages_rebuilds_user_attachments():
    chat_id = "11111111-1111-1111-1111-111111111111"
    rows = [
        {
            "chat_id": chat_id,
            "role": "user",
            "message_type": "text",
            "content": "Summarize this",
            "metadata": {
                "attachments": [
                    {
                        "id": "att-1",
                        "filename": "report.pdf",
                        "mime_type": "application/pdf",
                        "size_bytes": 100,
                        "provider": "azure_anthropic",
                        "provider_file_id": "file_abc123",
                    }
                ]
            },
            "sequence": 1,
        }
    ]

    messages = to_maf_messages(rows)
    assert len(messages) == 1
    assert messages[0].role == "user"
    assert len(messages[0].contents) == 2
    assert messages[0].contents[0].type == "text"
    assert messages[0].contents[0].text == "Summarize this"
    assert messages[0].contents[1].type == "hosted_file"
    assert messages[0].contents[1].file_id == "file_abc123"


def test_build_user_run_input_with_attachments():
    attachment = _Attachment()
    run_input = build_user_run_input("Analyze", [attachment])
    assert isinstance(run_input, Message)
    assert run_input.role == "user"
    assert len(run_input.contents) == 2
    assert run_input.contents[0].type == "text"
    assert run_input.contents[1].type == "hosted_file"


def test_build_user_run_input_text_only():
    assert build_user_run_input("hello", []) == "hello"
