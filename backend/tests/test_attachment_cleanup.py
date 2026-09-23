from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.platform.attachments.cleanup import (
    blob_paths_for_attachment,
    delete_attachment_storage,
)
from app.platform.docstore.manifest import iter_manifest_storage_paths


def test_iter_manifest_storage_paths_deduplicates():
    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    manifest = {
        "prefix": f"chat-attachments/{chat_id}/parsed/{attachment_id}",
        "artifacts": {
            "content_md": {
                "storage_path": f"chat-attachments/{chat_id}/parsed/{attachment_id}/content.md",
            },
            "meta_json": {
                "storage_path": f"chat-attachments/{chat_id}/parsed/{attachment_id}/meta.json",
            },
        },
    }
    paths = iter_manifest_storage_paths(manifest)
    assert paths == [
        f"chat-attachments/{chat_id}/parsed/{attachment_id}",
        f"chat-attachments/{chat_id}/parsed/{attachment_id}/content.md",
        f"chat-attachments/{chat_id}/parsed/{attachment_id}/meta.json",
    ]


def test_blob_paths_for_attachment_includes_original(monkeypatch):
    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    row = SimpleNamespace(
        id=attachment_id,
        chat_id=chat_id,
        provider="inline",
        provider_file_id=f"inline:{attachment_id}",
        parsed_artifact_manifest={
            "artifacts": {
                "meta_json": {
                    "storage_path": f"chat-attachments/{chat_id}/parsed/{attachment_id}/meta.json",
                }
            }
        },
    )
    monkeypatch.setattr("app.platform.attachments.cleanup.blob_storage_enabled", lambda: True)

    paths = blob_paths_for_attachment(row)
    assert paths[0] == f"chat-attachments/{chat_id}/{attachment_id}"
    assert f"chat-attachments/{chat_id}/parsed/{attachment_id}/meta.json" in paths


def test_delete_attachment_storage_deletes_blob_before_db_consumer(monkeypatch):
    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    row = SimpleNamespace(
        id=attachment_id,
        chat_id=chat_id,
        provider="inline",
        provider_file_id=f"inline:{attachment_id}",
        parsed_artifact_manifest={
            "prefix": f"chat-attachments/{chat_id}/parsed/{attachment_id}",
            "artifacts": {
                "content_md": {
                    "storage_path": f"chat-attachments/{chat_id}/parsed/{attachment_id}/content.md",
                }
            },
        },
    )
    calls: list[str] = []

    monkeypatch.setattr("app.platform.attachments.cleanup.blob_storage_enabled", lambda: True)
    monkeypatch.setattr(
        "app.platform.attachments.cleanup.blob_paths_for_attachment",
        lambda _row: [f"chat-attachments/{chat_id}/{attachment_id}"],
    )
    monkeypatch.setattr(
        "app.platform.attachments.cleanup.blob_delete",
        lambda path: calls.append(f"delete:{path}") or True,
    )
    monkeypatch.setattr(
        "app.platform.attachments.cleanup.blob_delete_prefix",
        lambda prefix: calls.append(f"prefix:{prefix}") or 1,
    )

    delete_attachment_storage(row)

    assert calls == [
        f"delete:chat-attachments/{chat_id}/{attachment_id}",
        f"prefix:chat-attachments/{chat_id}/parsed/{attachment_id}",
    ]


@pytest.mark.asyncio
async def test_attachment_service_delete_order(monkeypatch):
    from app.platform.attachments.service import AttachmentService

    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    row = SimpleNamespace(id=attachment_id, chat_id=chat_id)
    order: list[str] = []

    class _Repo:
        async def get(self, att_id):
            assert att_id == attachment_id
            return row

        async def delete(self, cid, att_id):
            assert cid == chat_id and att_id == attachment_id
            order.append("db")

    class _ParseJobs:
        async def delete_for_attachment(self, att_id):
            assert att_id == attachment_id
            order.append("parse_jobs")

    class _Db:
        async def commit(self):
            order.append("commit")

    monkeypatch.setattr(
        "app.platform.attachments.service.delete_attachment_storage",
        lambda _row: order.append("storage"),
    )
    monkeypatch.setattr(
        "app.platform.attachments.service.AttachmentRepository",
        lambda _db: _Repo(),
    )
    monkeypatch.setattr(
        "app.platform.attachments.service.ParseJobRepository",
        lambda _db: _ParseJobs(),
    )

    service = AttachmentService(_Db())  # type: ignore[arg-type]
    await service.delete(chat_id, attachment_id)

    assert order == ["storage", "parse_jobs", "db", "commit"]
