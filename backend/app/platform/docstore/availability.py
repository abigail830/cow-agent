"""Check which parsed artifact blobs exist for an attachment."""

from __future__ import annotations

import uuid

from app.platform.docstore.blob import parsed_artifact_exists

_ARTIFACT_KEYS = ("content_md", "meta_json", "pageindex_json")


def parsed_artifacts_availability(
    chat_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> dict[str, bool]:
    return {
        key: parsed_artifact_exists(chat_id, attachment_id, key)
        for key in _ARTIFACT_KEYS
    }
