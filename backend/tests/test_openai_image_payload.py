import base64

import pytest
from agent_framework import Content, Message

from app.platform.llm.openai_compatible_client import OpenAICompatibleReasoningClient
from app.platform.llm.openai_image_payload import sanitize_openai_image_payloads


def test_sanitize_reenco_valid_png():
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
    b64 = base64.b64encode(raw).decode()
    prepared = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "看"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ],
        }
    ]
    sanitized = sanitize_openai_image_payloads(prepared)
    url = sanitized[0]["content"][1]["image_url"]["url"]
    assert url.startswith("data:image/")
    payload = base64.b64decode(url.split(",", 1)[1])
    assert payload[:3] == b"\xff\xd8\xff" or payload[:8] == b"\x89PNG\r\n\x1a\n"


def test_sanitize_rejects_corrupt_png_magic():
    bad = b"\x89PNG\r\n\x1a\n" + b"x" * 64
    b64 = base64.b64encode(bad).decode()
    prepared = [
        {
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}],
        }
    ]
    with pytest.raises(ValueError, match="无法被模型识别"):
        sanitize_openai_image_payloads(prepared)


def test_sanitize_rejects_unreadable_bytes():
    bad = b"not-an-image"
    b64 = base64.b64encode(bad).decode()
    prepared = [
        {
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}],
        }
    ]
    with pytest.raises(ValueError, match="无法被模型识别"):
        sanitize_openai_image_payloads(prepared)


def test_openai_compatible_client_blocks_corrupt_image_before_api():
    bad = b"\x89PNG\r\n\x1a\n" + b"x" * 64
    content = Content.from_data(data=bad, media_type="image/png")
    message = Message(role="user", contents=[Content.from_text("看"), content])
    client = OpenAICompatibleReasoningClient.__new__(OpenAICompatibleReasoningClient)
    with pytest.raises(ValueError, match="无法被模型识别"):
        OpenAICompatibleReasoningClient._prepare_messages_for_openai(client, [message])
