from __future__ import annotations

import uuid

from app.platform.audio_capture.signed_urls import mint_asr_file_token, verify_asr_file_token


def test_asr_signed_url_roundtrip(monkeypatch) -> None:
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-signing-key")
    from app.config import get_settings

    get_settings.cache_clear()

    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    token, _expires = mint_asr_file_token(chat_id=chat_id, attachment_id=attachment_id)
    payload = verify_asr_file_token(token)
    assert payload["chat_id"] == str(chat_id)
    assert payload["attachment_id"] == str(attachment_id)
