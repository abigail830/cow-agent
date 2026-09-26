from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.platform.doc_retrieval.store import build_chat_library


@pytest.mark.asyncio
async def test_build_chat_library_uses_transcript_host_per_capture() -> None:
    chat_id = uuid.uuid4()
    host_id = uuid.uuid4()
    host = SimpleNamespace(
        id=host_id,
        filename="Meeting notes.md",
        mime_type="text/markdown",
        parse_status="ready",
        attachment_role="transcript_host",
        parsed_artifact_manifest={"artifacts": {"content_md": {}, "meta_json": {}}},
        gist=None,
        created_at=None,
    )
    part = SimpleNamespace(
        id=uuid.uuid4(),
        filename="clip.m4a",
        mime_type="audio/x-m4a",
        parse_status="skipped",
        attachment_role="audio_part",
        parsed_artifact_manifest=None,
        gist=None,
        created_at=None,
    )

    with (
        patch("app.platform.doc_retrieval.store.AttachmentRepository") as repo_cls,
        patch("app.platform.doc_retrieval.store.load_parsed_artifact") as load_parsed,
    ):
        repo_cls.return_value.list_for_chat = AsyncMock(return_value=[host, part])
        load_parsed.return_value = b'{"line_count": 3}'

        library = await build_chat_library(AsyncMock(), chat_id)

    assert str(host_id) in library
    assert library[str(host_id)].filename == "Meeting notes.md"
    assert all(entry.filename != "clip.m4a" for entry in library.values())
