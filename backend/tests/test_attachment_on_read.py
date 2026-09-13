import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.platform.attachments.materialization.on_read import (
    attachment_needs_lazy_materialization,
    materialize_attachment_item_async,
    materialize_row_attachments_sync,
    snapshot_is_resolved,
)
from app.platform.attachments.materialization.stub import format_unmaterialized_attachment_notice
from app.platform.memory.maf_mapping import to_maf_messages

CHAT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
MESSAGE_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
ATTACHMENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def _legacy_doc_item(*, with_snapshot: bool = False) -> dict:
    item: dict = {
        "id": str(ATTACHMENT_ID),
        "filename": "report.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size_bytes": 512,
        "provider": "unify_lite",
        "provider_file_id": f"inline:{ATTACHMENT_ID}",
    }
    if with_snapshot:
        item["extracted_snapshot"] = {
            "content_hash": "sha256:abc",
            "text": "Revenue increased 12%.",
            "truncated": False,
            "char_count": 22,
            "extracted_at": "2026-01-01T00:00:00+00:00",
        }
    return item


def _legacy_row(item: dict) -> dict:
    return {
        "id": str(MESSAGE_ID),
        "chat_id": str(CHAT_ID),
        "role": "user",
        "message_type": "text",
        "content": "Summarize the report",
        "sequence": 1,
        "metadata": {
            "attachment_mode": "unify_lite",
            "attachments": [item],
        },
    }


def test_legacy_doc_without_snapshot_needs_lazy_materialization() -> None:
    assert attachment_needs_lazy_materialization(_legacy_doc_item()) is True


def test_resolved_snapshot_skips_lazy_materialization() -> None:
    item = _legacy_doc_item(with_snapshot=True)
    assert snapshot_is_resolved(item) is True
    assert attachment_needs_lazy_materialization(item) is False


def test_lazy_extract_success_then_no_reextract(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []

    def _fake_load(_chat_id: uuid.UUID, _attachment_id: uuid.UUID) -> bytes:
        calls.append("load")
        return b"doc-bytes"

    monkeypatch.setattr(
        "app.platform.attachments.materialization.on_read.load_inline_attachment",
        _fake_load,
    )
    monkeypatch.setattr(
        "app.platform.attachments.materialization.on_read.extract_bytes",
        lambda **_kwargs: ("Revenue increased 12%.", [], 1),
    )

    row = _legacy_row(_legacy_doc_item())
    first = materialize_row_attachments_sync(row, chat_id=CHAT_ID, timeout_seconds=2.0)
    snapshot = first["metadata"]["attachments"][0]["extracted_snapshot"]
    assert "Revenue increased 12%" in snapshot["text"]
    assert snapshot.get("materialized_via") == "lazy_on_read"

    calls.clear()
    materialize_row_attachments_sync(first, chat_id=CHAT_ID, timeout_seconds=2.0)
    assert calls == []


def test_missing_blob_uses_neutral_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.platform.attachments.materialization.on_read.load_inline_attachment",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("missing")),
    )
    row = _legacy_row(_legacy_doc_item())
    resolved = materialize_row_attachments_sync(row, chat_id=CHAT_ID)
    snapshot = resolved["metadata"]["attachments"][0]["extracted_snapshot"]
    assert snapshot.get("materialize_failed") is True
    assert snapshot.get("failure_reason") == "blob_missing"
    assert "附件历史记录" in snapshot["text"]
    assert "请重新 @" not in snapshot["text"]


def test_unsupported_format_graceful_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.platform.attachments.materialization.on_read.load_inline_attachment",
        lambda *_args, **_kwargs: b"data",
    )
    monkeypatch.setattr(
        "app.platform.attachments.materialization.on_read.extract_bytes",
        lambda **_kwargs: (_ for _ in ()).throw(ValueError("unsupported")),
    )
    row = _legacy_row(_legacy_doc_item())
    resolved = materialize_row_attachments_sync(row, chat_id=CHAT_ID)
    snapshot = resolved["metadata"]["attachments"][0]["extracted_snapshot"]
    assert snapshot.get("materialize_failed") is True
    assert snapshot.get("failure_reason") == "unsupported_format"


def test_extract_timeout_falls_back_to_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    def _slow_extract(**_kwargs: object) -> tuple[str, list[str], int]:
        time.sleep(0.2)
        return "late", [], 1

    monkeypatch.setattr(
        "app.platform.attachments.materialization.on_read.load_inline_attachment",
        lambda *_args, **_kwargs: b"data",
    )
    monkeypatch.setattr(
        "app.platform.attachments.materialization.on_read.extract_bytes",
        _slow_extract,
    )
    row = _legacy_row(_legacy_doc_item())
    resolved = materialize_row_attachments_sync(row, chat_id=CHAT_ID, timeout_seconds=0.05)
    snapshot = resolved["metadata"]["attachments"][0]["extracted_snapshot"]
    assert snapshot.get("materialize_failed") is True
    assert snapshot.get("failure_reason") == "extract_timeout"


def test_replay_legacy_doc_after_lazy_extract_does_not_load_raw_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.platform.attachments.materialization.on_read.load_inline_attachment",
        lambda *_args, **_kwargs: b"doc-bytes",
    )
    monkeypatch.setattr(
        "app.platform.attachments.materialization.on_read.extract_bytes",
        lambda **_kwargs: ("Quarterly revenue up 12%.", [], 1),
    )
    row = materialize_row_attachments_sync(_legacy_row(_legacy_doc_item()), chat_id=CHAT_ID)

    load_calls: list[str] = []

    def _guard_load(*_args, **_kwargs) -> bytes:
        load_calls.append("load")
        return b"raw"

    monkeypatch.setattr(
        "app.platform.attachments.native.maf_content.load_inline_attachment",
        _guard_load,
    )
    messages = to_maf_messages([row])
    attachment_text = messages[0].contents[1].text or ""
    assert "Quarterly revenue up 12%" in attachment_text
    assert load_calls == []


@pytest.mark.asyncio
async def test_concurrent_lazy_materialize_persists_once(monkeypatch: pytest.MonkeyPatch) -> None:
    extract_calls = 0

    def _extract(**_kwargs: object) -> tuple[str, list[str], int]:
        nonlocal extract_calls
        extract_calls += 1
        return "Concurrent-safe text.", [], 1

    monkeypatch.setattr(
        "app.platform.attachments.materialization.on_read.load_inline_attachment",
        lambda *_args, **_kwargs: b"doc",
    )
    monkeypatch.setattr(
        "app.platform.attachments.materialization.on_read.extract_bytes",
        _extract,
    )

    stored_metadata = {
        "attachment_mode": "unify_lite",
        "attachments": [_legacy_doc_item()],
    }
    message = MagicMock()
    message.message_metadata = dict(stored_metadata)

    repo = MagicMock()
    repo.get = AsyncMock(return_value=message)
    repo.flush = AsyncMock()

    attachment_row = MagicMock()
    attachment_row.chat_id = CHAT_ID
    att_repo = MagicMock()
    att_repo.get = AsyncMock(return_value=attachment_row)

    monkeypatch.setattr(
        "app.platform.attachments.materialization.on_read.MessageRepository",
        lambda _session: repo,
    )
    monkeypatch.setattr(
        "app.platform.attachments.materialization.on_read.AttachmentRepository",
        lambda _session: att_repo,
    )

    session = AsyncMock()
    item = _legacy_doc_item()

    async def _run_once() -> None:
        await materialize_attachment_item_async(
            session,
            chat_id=CHAT_ID,
            message_id=MESSAGE_ID,
            item=dict(item),
        )

    import asyncio

    await asyncio.gather(_run_once(), _run_once())
    assert extract_calls == 1
    assert repo.flush.await_count >= 1
