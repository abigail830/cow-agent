import struct
import uuid
import zlib

from agent_framework import Content

from app.platform.attachments.materialize import materialize_attachments


def _minimal_png() -> bytes:
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
from app.platform.attachments.providers.adapters import should_use_azure_inline_image
from app.platform.attachments.storage import (
    format_inline_provider_file_id,
    is_inline_provider_file_id,
    load_inline_attachment,
    save_inline_attachment,
)


def test_should_use_azure_inline_image_for_png():
    assert should_use_azure_inline_image(
        base_url="https://example.cognitiveservices.azure.com/openai",
        mime_type="image/png",
    )
    assert not should_use_azure_inline_image(
        base_url="https://api.openai.com/v1",
        mime_type="image/png",
    )


def test_inline_provider_file_id_roundtrip():
    attachment_id = uuid.uuid4()
    provider_file_id = format_inline_provider_file_id(attachment_id)
    assert is_inline_provider_file_id(provider_file_id)


class _InlineAttachment:
    def __init__(self, chat_id: uuid.UUID, attachment_id: uuid.UUID) -> None:
        self.id = attachment_id
        self.chat_id = chat_id
        self.provider_file_id = format_inline_provider_file_id(attachment_id)
        self.mime_type = "image/png"
        self.filename = "screenshot.png"
        self.size_bytes = 8
        self.provider = "azure_openai"


def test_materialize_inline_image(tmp_path, monkeypatch):
    import app.platform.attachments.storage as attachment_storage

    monkeypatch.setattr(attachment_storage, "blob_storage_enabled", lambda: False)
    monkeypatch.setattr(attachment_storage, "INLINE_ATTACHMENTS_ROOT", tmp_path)

    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    save_inline_attachment(chat_id, attachment_id, _minimal_png())

    parts = materialize_attachments(
        [_InlineAttachment(chat_id, attachment_id)],
        chat_id=chat_id,
        provider="azure_openai",
    )
    assert len(parts) == 1
    content = parts[0]
    assert isinstance(content, Content)
    assert content.type == "data"
    assert content.media_type in {"image/png", "image/jpeg"}


def test_materialize_metadata_inline_image(tmp_path, monkeypatch):
    import app.platform.attachments.storage as attachment_storage

    monkeypatch.setattr(attachment_storage, "blob_storage_enabled", lambda: False)
    monkeypatch.setattr(attachment_storage, "INLINE_ATTACHMENTS_ROOT", tmp_path)

    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    save_inline_attachment(chat_id, attachment_id, _minimal_png())

    item = {
        "id": str(attachment_id),
        "filename": "screenshot.png",
        "mime_type": "image/png",
        "provider_file_id": format_inline_provider_file_id(attachment_id),
    }
    parts = materialize_attachments([item], chat_id=chat_id, provider="azure_openai")
    assert parts
    assert parts[0].type == "data"


def test_save_inline_attachment_uses_blob_when_enabled(monkeypatch):
    import app.platform.attachments.storage as attachment_storage

    stored: dict[str, bytes] = {}

    monkeypatch.setattr(attachment_storage, "blob_storage_enabled", lambda: True)

    def fake_put(pathname: str, body: bytes, *, content_type: str) -> dict:
        stored[pathname] = body
        return {"pathname": pathname}

    def fake_get(pathname: str) -> bytes | None:
        return stored.get(pathname)

    monkeypatch.setattr(attachment_storage, "blob_put", fake_put)
    monkeypatch.setattr(attachment_storage, "blob_get", fake_get)

    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    payload = b"\x89PNG\r\n\x1a\n"
    save_inline_attachment(chat_id, attachment_id, payload)

    key = f"chat-attachments/{chat_id}/{attachment_id}"
    assert stored[key] == payload
    assert load_inline_attachment(chat_id, attachment_id) == payload
