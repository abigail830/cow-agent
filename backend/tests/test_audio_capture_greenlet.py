"""Integration coverage for AsyncSession + capture submit serialization."""

from __future__ import annotations

import os
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

from app.db.models import Chat
from app.db.session import get_async_session_factory, init_db_engine
from app.platform.audio_capture.service import AudioCaptureService


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not configured — skip capture greenlet integration test",
)


@pytest.mark.asyncio
async def test_submit_capture_from_blob_parts_survives_post_flush_serialize() -> None:
    init_db_engine()
    factory = get_async_session_factory()
    async with factory() as session:
        chat_id = (await session.execute(text("SELECT id FROM chats LIMIT 1"))).scalar_one()
        chat = await session.get(Chat, chat_id)
        assert chat is not None
        part_id = uuid.uuid4()

        with (
            patch("app.platform.audio_capture.service.blob_storage_enabled", return_value=True),
            patch("app.platform.audio_capture.service.blob_exists_async", AsyncMock(return_value=True)),
            patch(
                "app.platform.audio_capture.service.load_asr_context_for_chat",
                AsyncMock(return_value=None),
            ),
            patch(
                "app.platform.audio_capture.service.enqueue_capture_parse_job",
                AsyncMock(side_effect=lambda _session, *, capture, host_row: host_row),
            ),
        ):
            service = AudioCaptureService(session)
            result = await service.submit_capture_from_blob_parts(
                chat,
                title="Integration test",
                parts=[
                    {
                        "attachment_id": str(part_id),
                        "sort_order": 0,
                        "filename": "clip.m4a",
                        "mime_type": "audio/mp4",
                        "size_bytes": 1024,
                    }
                ],
            )

        assert result["status"] == "running"
        assert result["updated_at"] is not None
        await session.rollback()
