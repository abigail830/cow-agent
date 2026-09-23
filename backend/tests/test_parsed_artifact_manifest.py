from __future__ import annotations

import uuid

from app.platform.docstore.manifest import (
    merge_parsed_artifact_record,
    parsed_artifacts_flags_from_manifest,
)


def test_merge_parsed_artifact_record_tracks_storage_path(monkeypatch):
    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    monkeypatch.setattr("app.platform.docstore.manifest.blob_storage_enabled", lambda: False)

    manifest = merge_parsed_artifact_record(
        None,
        chat_id=chat_id,
        attachment_id=attachment_id,
        artifact_key="content_md",
        size_bytes=128,
        content_type="text/markdown; charset=utf-8",
    )

    assert manifest["storage"] == "local"
    assert manifest["prefix"] == f"chat-attachments/{chat_id}/parsed/{attachment_id}"
    record = manifest["artifacts"]["content_md"]
    assert record["relative_path"] == "content.md"
    assert record["storage_path"].endswith("/content.md")
    assert record["size_bytes"] == 128

    manifest = merge_parsed_artifact_record(
        manifest,
        chat_id=chat_id,
        attachment_id=attachment_id,
        artifact_key="meta_json",
        size_bytes=64,
        content_type="application/json",
    )
    flags = parsed_artifacts_flags_from_manifest(manifest)
    assert flags == {
        "content_md": True,
        "meta_json": True,
        "pageindex_json": False,
    }


def test_parsed_artifacts_flags_from_manifest_empty():
    empty = {
        "content_md": False,
        "meta_json": False,
        "pageindex_json": False,
    }
    assert parsed_artifacts_flags_from_manifest(None) == empty
    assert parsed_artifacts_flags_from_manifest({}) == empty
