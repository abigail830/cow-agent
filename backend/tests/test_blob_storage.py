import uuid
from unittest.mock import MagicMock

from app.config import get_settings
from app.proposal import blob_client, storage


def _upload_bytes(uploads: list[tuple[str, bytes | str, str]], pathname: str) -> bytes | None:
    for path, body, _ in uploads:
        if path == pathname:
            return body.encode("utf-8") if isinstance(body, str) else body
    return None


def test_save_diagram_artifact_to_blob(monkeypatch):
    chat_id = uuid.uuid4()
    artifact_id = "diag-blob123"
    uploads: list[tuple[str, bytes | str, str]] = []

    monkeypatch.setattr(storage, "blob_storage_enabled", lambda: True)

    def fake_put(pathname: str, body: bytes | str, *, content_type: str):
        uploads.append((pathname, body, content_type))
        return {"pathname": pathname, "url": f"https://example.blob/{pathname}"}

    monkeypatch.setattr(storage, "blob_put", fake_put)
    monkeypatch.setattr(
        storage,
        "blob_get",
        lambda pathname: _upload_bytes(uploads, pathname),
    )

    storage.save_diagram_artifact(
        chat_id,
        artifact_id,
        svg="<svg></svg>",
        png=b"\x89PNG",
        filename_base="flow",
    )

    assert len(uploads) == 3
    payload = storage.load_artifact_payload(chat_id, artifact_id)
    assert payload is not None
    assert payload.data == b"<svg></svg>"
    assert payload.filename == "flow.svg"


def test_blob_put_uses_token(monkeypatch):
    monkeypatch.setenv(
        "BLOB_READ_WRITE_TOKEN",
        "vercel_blob_rw_teststore_testsecret",
    )
    monkeypatch.setenv("ARTIFACT_STORAGE", "vercel_blob")
    monkeypatch.setenv("BLOB_ACCESS", "private")
    monkeypatch.setenv("BLOB_STORE_ID", "teststore")
    get_settings.cache_clear()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"pathname": "demo.txt", "url": "https://example/demo.txt"}

    mock_client = MagicMock()
    mock_client.__enter__.return_value = mock_client
    mock_client.put.return_value = mock_response
    monkeypatch.setattr(blob_client.httpx, "Client", lambda **kwargs: mock_client)

    result = blob_client.blob_put("demo.txt", b"hello", content_type="text/plain")
    assert result["pathname"] == "demo.txt"
    call_url = mock_client.put.call_args.args[0]
    assert call_url.startswith("https://vercel.com/api/blob/?pathname=")
    headers = mock_client.put.call_args.kwargs["headers"]
    assert headers["authorization"] == "Bearer vercel_blob_rw_teststore_testsecret"
    assert headers["x-vercel-blob-access"] == "private"
    assert headers["x-vercel-blob-store-id"] == "teststore"

    get_settings.cache_clear()
