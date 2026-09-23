from __future__ import annotations

import uuid
from pathlib import Path

from app.platform.docstore.blob import parsed_artifact_exists


def test_parsed_artifact_exists_uses_stat_not_full_read(monkeypatch, tmp_path: Path):
    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    artifact_dir = tmp_path / str(chat_id) / "parsed" / str(attachment_id)
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "content.md").write_text("# hello", encoding="utf-8")

    monkeypatch.setattr("app.platform.docstore.blob.blob_storage_enabled", lambda: False)
    monkeypatch.setattr(
        "app.platform.docstore.blob.parsed_artifact_path",
        lambda _chat_id, _attachment_id, artifact_key: artifact_dir
        / {"content_md": "content.md", "meta_json": "meta.json", "pageindex_json": "pageindex.json"}[
            artifact_key
        ],
    )

    read_calls = {"count": 0}

    def fail_read_bytes(_self):
        read_calls["count"] += 1
        raise AssertionError("parsed_artifact_exists should not read file contents")

    monkeypatch.setattr(Path, "read_bytes", fail_read_bytes, raising=False)

    assert parsed_artifact_exists(chat_id, attachment_id, "content_md") is True
    assert parsed_artifact_exists(chat_id, attachment_id, "meta_json") is False
    assert read_calls["count"] == 0


def test_blob_exists_uses_head_not_get(monkeypatch):
    from unittest.mock import MagicMock

    from app.agent_specific.proposal import blob_client
    from app.config import get_settings

    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", "vercel_blob_rw_teststore_testsecret")
    monkeypatch.setenv("ARTIFACT_STORAGE", "vercel_blob")
    monkeypatch.setenv("BLOB_ACCESS", "private")
    monkeypatch.setenv("BLOB_STORE_ID", "teststore")
    get_settings.cache_clear()

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.head.return_value = MagicMock(status_code=200)
    monkeypatch.setattr(blob_client.httpx, "Client", lambda **kwargs: mock_client)

    assert blob_client.blob_exists("chat-attachments/demo/content.md") is True
    mock_client.head.assert_called_once()
    mock_client.get.assert_not_called()

    get_settings.cache_clear()
