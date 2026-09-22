import uuid
from unittest.mock import patch

from agent_framework import Content, Message

from app.platform.attachments.materialize import materialize_attachments
from app.platform.llm.openai_compatible_client import OpenAICompatibleReasoningClient
from app.platform.memory.maf_mapping import to_maf_messages


def test_deepseek_image_uses_hosted_file_id():
    chat_id = uuid.uuid4()
    item = {
        "id": str(uuid.uuid4()),
        "filename": "shot.png",
        "mime_type": "image/png",
        "size_bytes": 12,
        "provider": "deepseek",
        "provider_file_id": "file-deepseek-1",
    }
    parts = materialize_attachments(
        [item],
        chat_id=chat_id,
        model_id="deepseek-flash",
        provider="deepseek",
    )
    assert len(parts) == 1
    assert parts[0].type == "hosted_file"
    assert parts[0].file_id == "file-deepseek-1"


def test_qwen_pdf_uses_file_data(monkeypatch):
    chat_id = uuid.uuid4()
    att_id = uuid.uuid4()
    pdf = b"%PDF-1.4 fake"
    monkeypatch.setattr(
        "app.platform.attachments.materialize.load_attachment_bytes",
        lambda *_args, **_kwargs: pdf,
    )
    item = {
        "id": str(att_id),
        "filename": "brief.pdf",
        "mime_type": "application/pdf",
        "size_bytes": len(pdf),
        "provider": "dashscope",
        "provider_file_id": f"inline:{att_id}",
    }
    parts = materialize_attachments(
        [item],
        chat_id=chat_id,
        model_id="qwen3.8-max",
        provider="dashscope",
    )
    assert len(parts) == 1
    assert parts[0].type == "data"
    assert parts[0].media_type == "application/pdf"


def test_claude_pdf_uses_hosted_file():
    chat_id = uuid.uuid4()
    item = {
        "id": str(uuid.uuid4()),
        "filename": "brief.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 100,
        "provider": "azure_anthropic",
        "provider_file_id": "file_abc123",
    }
    parts = materialize_attachments(
        [item],
        chat_id=chat_id,
        model_id="claude-sonnet-4-6",
        provider="azure_anthropic",
    )
    assert parts[0].type == "hosted_file"
    assert parts[0].file_id == "file_abc123"


def test_to_maf_messages_rebuilds_hosted_pdf_without_model_id():
    chat_id = str(uuid.uuid4())
    rows = [
        {
            "chat_id": chat_id,
            "role": "user",
            "message_type": "text",
            "content": "Summarize this",
            "metadata": {
                "attachments": [
                    {
                        "id": str(uuid.uuid4()),
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
    assert messages[0].contents[1].type == "hosted_file"
    assert messages[0].contents[1].file_id == "file_abc123"


def test_openai_compatible_client_maps_hosted_file():
    client = OpenAICompatibleReasoningClient.__new__(OpenAICompatibleReasoningClient)
    message = Message(
        role="user",
        contents=[
            Content.from_text("see image"),
            Content.from_hosted_file(file_id="file-1", media_type="image/png", name="a.png"),
        ],
    )

    def fake_super(_self, stripped):
        texts = [
            getattr(content, "text", "")
            for content in (stripped.contents or [])
            if getattr(content, "type", None) == "text"
        ]
        return [{"role": "user", "content": "".join(texts) or ""}]

    with patch(
        "app.platform.llm.openai_compatible_client.OpenAIChatCompletionClient._prepare_message_for_openai",
        fake_super,
    ):
        prepared = OpenAICompatibleReasoningClient._prepare_message_for_openai(client, message)

    assert prepared[0]["content"][-1] == {"type": "file", "file_id": "file-1"}
    assert prepared[0]["content"][0] == {"type": "text", "text": "see image"}
