from __future__ import annotations

import uuid

from app.platform.docstore.manifest import merge_parsed_artifact_record, parsed_artifacts_flags_from_manifest


def test_batch_manifest_merge_includes_all_artifact_keys():
    """One batch transaction merges every key onto the same manifest (no lost updates)."""
    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    manifest = None
    for key, size in (
        ("content_md", 1200),
        ("meta_json", 800),
        ("pageindex_json", 400),
    ):
        manifest = merge_parsed_artifact_record(
            manifest,
            chat_id=chat_id,
            attachment_id=attachment_id,
            artifact_key=key,
            size_bytes=size,
            content_type="application/json",
        )
    flags = parsed_artifacts_flags_from_manifest(manifest)
    assert flags == {
        "content_md": True,
        "meta_json": True,
        "pageindex_json": True,
    }
