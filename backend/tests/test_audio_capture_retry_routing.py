from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.platform.attachments.parse_ingest import retry_attachment_parse


@pytest.mark.asyncio
async def test_retry_attachment_parse_routes_transcript_host_to_capture_enqueue() -> None:
    host_id = uuid.uuid4()
    capture_id = uuid.uuid4()
    host_row = SimpleNamespace(
        id=host_id,
        filename="Audio transcript.md",
        mime_type="text/markdown",
        attachment_role="transcript_host",
    )
    capture = SimpleNamespace(id=capture_id)
    session = AsyncMock()

    with (
        patch(
            "app.db.repositories.audio_captures.AudioCaptureRepository.get_by_host_attachment",
            AsyncMock(return_value=capture),
        ) as get_capture,
        patch(
            "app.platform.audio_capture.enqueue.enqueue_capture_parse_job",
            AsyncMock(return_value=host_row),
        ) as enqueue_capture,
    ):
        result = await retry_attachment_parse(session, host_row)  # type: ignore[arg-type]

    get_capture.assert_awaited_once_with(host_id)
    enqueue_capture.assert_awaited_once()
    assert result is host_row
