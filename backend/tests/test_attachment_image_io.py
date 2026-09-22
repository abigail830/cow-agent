import uuid

import pytest

from app.platform.attachments.image_io import (
    prepare_image_for_storage,
    resolve_image_mime,
    sniff_image_mime,
    validate_image_bytes,
)
from app.platform.attachments.materialize import materialize_attachments
from app.platform.attachments.upload import AttachmentUploader
from agent_framework import Content
from agent_framework.openai import OpenAIChatCompletionClient


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


def test_sniff_image_mime_png():
    data = _minimal_png()
    assert sniff_image_mime(data) == "image/png"


def test_resolve_image_mime_prefers_sniff_over_octet_stream():
    data = _minimal_png()
    assert (
        resolve_image_mime(data=data, filename="shot.png", mime_type="application/octet-stream")
        == "image/png"
    )


def test_validate_image_bytes_rejects_truncated_png():
    with pytest.raises(ValueError, match="不是有效的图片"):
        validate_image_bytes(b"\x89PNG\r\n\x1a\n", filename="bad.png")


def test_prepare_image_for_storage_downscales_oversized_figma_png():
    from pathlib import Path

    import pymupdf as fitz

    from app.platform.attachments.image_io import LLM_VISION_MAX_SIDE

    path = Path(__file__).resolve().parents[2] / "docs" / "20260921-214918.png"
    if not path.is_file():
        pytest.skip("sample Figma export not in repo")
    raw = path.read_bytes()
    pix = fitz.Pixmap(raw)
    assert max(pix.width, pix.height) > LLM_VISION_MAX_SIDE

    normalized, mime = prepare_image_for_storage(
        raw,
        filename=path.name,
        mime_type="image/png",
    )
    out = fitz.Pixmap(normalized)
    assert max(out.width, out.height) <= LLM_VISION_MAX_SIDE
    assert mime in {"image/png", "image/jpeg"}


def test_prepare_image_for_storage_normalizes_png():
    data = _minimal_png()
    normalized, mime = prepare_image_for_storage(
        data,
        filename="shot.png",
        mime_type="application/octet-stream",
    )
    assert mime in {"image/png", "image/jpeg"}
    assert len(normalized) > 32
    validate_image_bytes(normalized, filename="shot.png")


def test_materialize_inline_image_uses_image_mime_for_openai(tmp_path, monkeypatch):
    import app.platform.attachments.storage as attachment_storage

    monkeypatch.setattr(attachment_storage, "blob_storage_enabled", lambda: False)
    monkeypatch.setattr(attachment_storage, "INLINE_ATTACHMENTS_ROOT", tmp_path)

    data = _minimal_png()
    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    attachment_storage.save_inline_attachment(chat_id, attachment_id, data)

    item = {
        "id": str(attachment_id),
        "filename": "shot.png",
        "mime_type": "application/octet-stream",
        "size_bytes": len(data),
        "provider": "deepseek",
        "provider_file_id": f"inline:{attachment_id}",
    }
    parts = materialize_attachments(
        [item],
        chat_id=chat_id,
        model_id="deepseek-flash",
        provider="deepseek",
    )
    assert len(parts) == 1
    content = parts[0]
    assert content.type == "data"
    assert content.media_type in {"image/png", "image/jpeg"}

    from agent_framework import Message

    message = Message(role="user", contents=[content])
    client = OpenAIChatCompletionClient.__new__(OpenAIChatCompletionClient)
    prepared = OpenAIChatCompletionClient._prepare_message_for_openai(client, message)
    body = prepared[0]["content"]
    assert isinstance(body, list)
    assert body[-1]["type"] == "image_url"
    assert body[-1]["image_url"]["url"].startswith("data:image/")
