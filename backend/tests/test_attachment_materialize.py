import uuid
from unittest.mock import patch

from agent_framework import Content, Message

from app.platform.attachments.materialize import (
    apply_attachment_reference_policy,
    format_attachment_reference_text,
    full_inline_attachment_ids_in_message,
    fully_inlined_attachment_ids_in_context,
    is_attachment_reference_text,
    materialize_attachments,
    prior_full_attachment_ids_in_context,
)
from app.platform.llm.openai_compatible_client import OpenAICompatibleReasoningClient
from app.platform.memory.maf_mapping import to_maf_messages


def _minimal_png() -> bytes:
    import struct
    import zlib

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    raw = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw += chunk(b"IHDR", ihdr)
    raw += chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
    raw += chunk(b"IEND", b"")
    return raw


def test_deepseek_image_uses_inline_data(tmp_path, monkeypatch):
    import app.platform.attachments.storage as attachment_storage

    monkeypatch.setattr(attachment_storage, "blob_storage_enabled", lambda: False)
    monkeypatch.setattr(attachment_storage, "INLINE_ATTACHMENTS_ROOT", tmp_path)

    chat_id = uuid.uuid4()
    att_id = uuid.uuid4()
    png = _minimal_png()
    attachment_storage.save_inline_attachment(chat_id, att_id, png)

    item = {
        "id": str(att_id),
        "filename": "shot.png",
        "mime_type": "image/png",
        "size_bytes": len(png),
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
    assert parts[0].type == "data"
    assert parts[0].media_type in {"image/png", "image/jpeg"}


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


def test_materialize_attachments_second_occurrence_is_reference():
    chat_id = uuid.uuid4()
    att_id = str(uuid.uuid4())
    item = {
        "id": att_id,
        "filename": "notes.txt",
        "mime_type": "text/plain",
        "size_bytes": 12,
    }
    already_full = {att_id}
    parts = materialize_attachments(
        [item],
        chat_id=chat_id,
        already_full_inlined=already_full,
    )
    assert len(parts) == 1
    assert parts[0].type == "text"
    assert is_attachment_reference_text(parts[0].text)
    assert att_id in parts[0].text


def test_to_maf_messages_second_attachment_mention_is_reference():
    chat_id = str(uuid.uuid4())
    att_id = str(uuid.uuid4())
    attachment = {
        "id": att_id,
        "filename": "report.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 100,
        "provider": "azure_anthropic",
        "provider_file_id": "file_abc123",
    }
    rows = [
        {
            "chat_id": chat_id,
            "role": "user",
            "message_type": "text",
            "content": "First look",
            "metadata": {"attachments": [attachment]},
            "sequence": 1,
        },
        {
            "chat_id": chat_id,
            "role": "user",
            "message_type": "text",
            "content": "Same file again",
            "metadata": {"attachments": [attachment]},
            "sequence": 2,
        },
    ]
    messages = to_maf_messages(rows)
    assert messages[0].contents[1].type == "hosted_file"
    assert messages[1].contents[1].type == "text"
    assert is_attachment_reference_text(messages[1].contents[1].text)


def test_apply_attachment_reference_policy_rewrites_stored_full_duplicates():
    chat_id = uuid.uuid4()
    att_id = str(uuid.uuid4())
    attachment = {
        "id": att_id,
        "filename": "report.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 100,
        "provider": "azure_anthropic",
        "provider_file_id": "file_abc123",
    }
    first = Message(
        role="user",
        contents=[
            Content.from_text("First look"),
            Content.from_hosted_file(
                file_id="file_abc123",
                media_type="application/pdf",
                name="report.pdf",
            ),
        ],
        additional_properties={"platform": {"attachments": [attachment]}},
    )
    second = Message(
        role="user",
        contents=[
            Content.from_text("Same file again"),
            Content.from_hosted_file(
                file_id="file_abc123",
                media_type="application/pdf",
                name="report.pdf",
            ),
        ],
        additional_properties={"platform": {"attachments": [attachment]}},
    )
    rewritten = apply_attachment_reference_policy([first, second], chat_id=chat_id)
    assert rewritten[0].contents[1].type == "hosted_file"
    assert rewritten[1].contents[1].type == "text"
    assert is_attachment_reference_text(rewritten[1].contents[1].text)


def test_full_inline_ignores_reference_inline_mode():
    att_id = str(uuid.uuid4())
    attachment = {
        "id": att_id,
        "filename": "shot.png",
        "mime_type": "image/png",
        "size_bytes": 12,
    }
    message = Message(
        role="user",
        contents=[
            Content.from_text("Earlier question"),
            Content.from_hosted_file(
                file_id="file-deepseek-1",
                media_type="image/png",
                name="shot.png",
            ),
        ],
        additional_properties={
            "platform": {
                "attachments": [attachment],
                "attachment_inline_modes": {att_id: "reference"},
            }
        },
    )
    assert full_inline_attachment_ids_in_message(message) == set()


def test_prior_full_uses_reference_policy_not_raw_db_duplicates():
    chat_id = uuid.uuid4()
    att_id = str(uuid.uuid4())
    attachment = {
        "id": att_id,
        "filename": "report.pdf",
        "mime_type": "application/pdf",
        "size_bytes": 100,
        "provider": "azure_anthropic",
        "provider_file_id": "file_abc123",
    }
    first = Message(
        role="user",
        contents=[
            Content.from_text("First look"),
            Content.from_hosted_file(
                file_id="file_abc123",
                media_type="application/pdf",
                name="report.pdf",
            ),
        ],
        additional_properties={"platform": {"attachments": [attachment]}},
    )
    second = Message(
        role="user",
        contents=[
            Content.from_text("Same file again"),
            Content.from_hosted_file(
                file_id="file_abc123",
                media_type="application/pdf",
                name="report.pdf",
            ),
        ],
        additional_properties={"platform": {"attachments": [attachment]}},
    )
    raw = fully_inlined_attachment_ids_in_context([first, second])
    assert att_id in raw
    prior = prior_full_attachment_ids_in_context([first, second], chat_id=chat_id)
    assert prior == {att_id}


def test_fully_inlined_requires_full_body_not_metadata_only():
    att_id = str(uuid.uuid4())
    attachment = {
        "id": att_id,
        "filename": "notes.txt",
        "mime_type": "text/plain",
        "size_bytes": 12,
    }
    message = Message(
        role="user",
        contents=[Content.from_text("Please review @notes.txt")],
        additional_properties={"platform": {"attachments": [attachment]}},
    )
    assert fully_inlined_attachment_ids_in_context([message]) == set()


def test_stubbed_attachment_reinlines_only_on_new_mention(monkeypatch):
    chat_id = uuid.uuid4()
    att_id = str(uuid.uuid4())
    attachment = {
        "id": att_id,
        "filename": "notes.txt",
        "mime_type": "text/plain",
        "size_bytes": 12,
    }
    stubbed = Message(
        role="user",
        contents=[
            Content.from_text("Earlier question"),
            Content.from_text(
                format_attachment_reference_text(
                    filename="notes.txt",
                    mime_type="text/plain",
                    size_bytes=12,
                    attachment_id=att_id,
                )
            ),
        ],
        additional_properties={
            "platform": {
                "attachments": [attachment],
                "attachment_inline_modes": {att_id: "reference"},
            }
        },
    )

    replayed = apply_attachment_reference_policy([stubbed], chat_id=chat_id)
    assert is_attachment_reference_text(replayed[0].contents[1].text)

    monkeypatch.setattr(
        "app.platform.attachments.materialize.load_attachment_bytes",
        lambda *_args, **_kwargs: b"hello world",
    )
    prior_full = fully_inlined_attachment_ids_in_context([stubbed])
    assert prior_full == set()
    parts = materialize_attachments(
        [attachment],
        chat_id=chat_id,
        already_full_inlined=set(prior_full),
    )
    assert parts[0].type == "text"
    assert not is_attachment_reference_text(parts[0].text)


def test_replay_rematerializes_stored_hosted_file_image_for_inline_caps(tmp_path, monkeypatch):
    import app.platform.attachments.storage as attachment_storage

    monkeypatch.setattr(attachment_storage, "blob_storage_enabled", lambda: False)
    monkeypatch.setattr(attachment_storage, "INLINE_ATTACHMENTS_ROOT", tmp_path)

    chat_id = uuid.uuid4()
    att_id = str(uuid.uuid4())
    png = _minimal_png()
    attachment_storage.save_inline_attachment(chat_id, uuid.UUID(att_id), png)
    attachment = {
        "id": att_id,
        "filename": "shot.png",
        "mime_type": "image/png",
        "size_bytes": len(png),
        "provider": "deepseek",
        "provider_file_id": "file-deepseek-old",
    }
    stored = Message(
        role="user",
        contents=[
            Content.from_text("see image"),
            Content.from_hosted_file(
                file_id="file-deepseek-old",
                media_type="image/png",
                name="shot.png",
            ),
        ],
        additional_properties={"platform": {"attachments": [attachment]}},
    )
    rewritten = apply_attachment_reference_policy(
        [stored],
        chat_id=chat_id,
        model_id="deepseek-flash",
        provider="deepseek",
    )
    assert rewritten[0].contents[1].type == "data"
    assert rewritten[0].contents[1].media_type in {"image/png", "image/jpeg"}


def test_openai_compatible_client_merges_text_and_image_user_message():
    client = OpenAICompatibleReasoningClient.__new__(OpenAICompatibleReasoningClient)
    message = Message(
        role="user",
        contents=[
            Content.from_text("看这图"),
            Content.from_uri(
                uri="data:image/jpeg;base64,/9j/4AAQ",
                media_type="image/jpeg",
            ),
        ],
    )
    prepared = OpenAICompatibleReasoningClient._prepare_message_for_openai(client, message)
    assert len(prepared) == 1
    body = prepared[0]["content"]
    assert isinstance(body, list)
    assert body[0]["type"] == "text"
    assert body[1]["type"] == "image_url"


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
