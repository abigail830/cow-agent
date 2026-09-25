from __future__ import annotations

import base64
import json

from app.platform.blob.client import generate_client_upload_token


def test_generate_client_upload_token_format(monkeypatch) -> None:
    token = "vercel_blob_rw_teststore_abc123_secret"
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", token)
    monkeypatch.setenv("ARTIFACT_STORAGE", "vercel_blob")
    from app.config import get_settings

    get_settings.cache_clear()

    client_token = generate_client_upload_token(
        "chat-attachments/chat-id/attachment-id",
        maximum_size_in_bytes=1024,
        allowed_content_types=["audio/*"],
        allow_overwrite=True,
    )
    assert client_token.startswith("vercel_blob_client_teststore_")

    encoded = client_token.removeprefix("vercel_blob_client_teststore_")
    decoded = base64.b64decode(encoded).decode("ascii")
    signature, payload_b64 = decoded.split(".", 1)
    assert len(signature) == 64

    payload = json.loads(base64.b64decode(payload_b64))
    assert payload["pathname"] == "chat-attachments/chat-id/attachment-id"
    assert payload["maximumSizeInBytes"] == 1024
    assert payload["allowedContentTypes"] == ["audio/*"]
    assert payload["allowOverwrite"] is True
