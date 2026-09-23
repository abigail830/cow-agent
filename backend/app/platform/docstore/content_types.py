"""Media types for parsed attachment artifacts."""

from __future__ import annotations

_PARSED_MEDIA_TYPES = {
    "content_md": "text/markdown; charset=utf-8",
    "meta_json": "application/json; charset=utf-8",
    "pageindex_json": "application/json; charset=utf-8",
}

VALID_PARSED_ARTIFACT_KEYS = frozenset(_PARSED_MEDIA_TYPES)


def parsed_artifact_media_type(artifact_key: str) -> str:
    return _PARSED_MEDIA_TYPES.get(artifact_key, "application/octet-stream")
