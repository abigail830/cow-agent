from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.config import get_settings
from app.platform.blob import client as blob_client


def test_build_presign_canonical_string_sorts_lines() -> None:
    canonical = blob_client._build_presign_canonical_string(
        pathname="chat-attachments/a/b",
        operation="get",
        presign_entries=[("vercel-blob-valid-until", "1700000000000")],
    )
    assert canonical.splitlines() == [
        "operation=get",
        "pathname=chat-attachments/a/b",
        "vercel-blob-valid-until=1700000000000",
    ]


def test_blob_presigned_get_url_builds_signed_blob_url(monkeypatch) -> None:
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "vercel_blob_rw_teststore_testsecret")
    monkeypatch.setenv("ARTIFACT_STORAGE", "vercel_blob")
    monkeypatch.setenv("BLOB_ACCESS", "private")
    monkeypatch.setenv("BLOB_STORE_ID", "teststore")
    get_settings.cache_clear()

    issued = {
        "delegationToken": "payload.sig",
        "clientSigningToken": "client-signing-key",
        "validUntil": 1_700_000_000_000,
    }
    monkeypatch.setattr(blob_client, "blob_issue_signed_token", lambda **kwargs: issued)

    captured: dict[str, str] = {}

    def fake_hmac(key: str, data: str) -> str:
        captured["key"] = key
        captured["data"] = data
        return "signed-value"

    monkeypatch.setattr(blob_client, "_hmac_sha256_base64url", fake_hmac)

    url = blob_client.blob_presigned_get_url(
        "chat-attachments/chat/part",
        valid_until_ms=1_700_000_000_000,
    )

    assert url.startswith("https://teststore.private.blob.vercel-storage.com/chat-attachments/chat/part?")
    assert "vercel-blob-delegation=payload.sig" in url
    assert "vercel-blob-signature=signed-value" in url
    assert captured["key"] == "client-signing-key"
    assert "operation=get" in captured["data"]
    assert "pathname=chat-attachments/chat/part" in captured["data"]


def test_mint_asr_download_url_uses_blob_presign_when_enabled(monkeypatch) -> None:
    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    monkeypatch.setattr(
        "app.platform.audio_capture.signed_urls.blob_storage_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.platform.audio_capture.signed_urls.blob_presigned_get_url",
        lambda pathname, valid_until_ms: f"https://blob.example/{pathname}?signed=1",
    )

    from app.platform.audio_capture.signed_urls import mint_asr_download_url

    url, expires_at = mint_asr_download_url(chat_id=chat_id, attachment_id=attachment_id)
    assert url.startswith("https://blob.example/chat-attachments/")
    assert expires_at > 0
