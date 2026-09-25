from __future__ import annotations

import json
import uuid

import pytest

from app.platform.audio_capture.blob_upload import handle_blob_upload_request


def test_handle_blob_upload_request_rejects_bad_pathname(monkeypatch) -> None:
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "vercel_blob_rw_teststore_abc123_secret")
    monkeypatch.setenv("ARTIFACT_STORAGE", "vercel_blob")
    from app.config import get_settings

    get_settings.cache_clear()

    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    with pytest.raises(ValueError, match="pathname"):
        handle_blob_upload_request(
            chat_id=chat_id,
            body={
                "type": "blob.generate-client-token",
                "payload": {
                    "pathname": "wrong/path",
                    "clientPayload": json.dumps(
                        {"chat_id": str(chat_id), "attachment_id": str(attachment_id)}
                    ),
                    "multipart": False,
                },
            },
        )


def test_handle_blob_upload_request_mints_token(monkeypatch) -> None:
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "vercel_blob_rw_teststore_abc123_secret")
    monkeypatch.setenv("ARTIFACT_STORAGE", "vercel_blob")
    from app.config import get_settings

    get_settings.cache_clear()

    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    pathname = f"chat-attachments/{chat_id}/{attachment_id}"
    result = handle_blob_upload_request(
        chat_id=chat_id,
        body={
            "type": "blob.generate-client-token",
            "payload": {
                "pathname": pathname,
                "clientPayload": json.dumps(
                    {"chat_id": str(chat_id), "attachment_id": str(attachment_id)}
                ),
                "multipart": True,
            },
        },
    )
    assert result["type"] == "blob.generate-client-token"
    assert result["clientToken"].startswith("vercel_blob_client_teststore_")
