from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.platform.audio_capture.service import AudioCaptureService


@pytest.mark.asyncio
async def test_submit_capture_from_blob_parts_uses_async_blob_exists(monkeypatch) -> None:
    chat_id = uuid.uuid4()
    part_id = uuid.uuid4()
    chat = SimpleNamespace(id=chat_id)

    blob_check_called = False

    async def fake_blob_exists_async(_pathname: str) -> bool:
        nonlocal blob_check_called
        blob_check_called = True
        return True

    monkeypatch.setattr("app.platform.audio_capture.service.blob_storage_enabled", lambda: True)
    monkeypatch.setattr(
        "app.platform.audio_capture.service.blob_exists_async",
        fake_blob_exists_async,
    )
    monkeypatch.setattr(
        "app.platform.audio_capture.service.load_asr_context_for_chat",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(
        "app.platform.audio_capture.service.enqueue_capture_parse_job",
        AsyncMock(side_effect=lambda _session, *, capture, host_row: host_row),
    )

    inserted_host_id = uuid.uuid4()

    class _Attachments:
        def __init__(self, _session) -> None:
            self._host_id = inserted_host_id

        async def insert(self, **kwargs):
            attachment_id = kwargs.get("attachment_id") or uuid.uuid4()
            role = kwargs.get("attachment_role")
            row = SimpleNamespace(
                id=attachment_id if role != "transcript_host" else self._host_id,
                parse_job_id="job_test",
                parse_status="running",
                parse_stage_snapshot=None,
            )
            if role == "transcript_host":
                self._host_id = row.id
            return row

        async def get(self, attachment_id):
            return SimpleNamespace(
                id=attachment_id,
                parse_status="running",
                parse_stage_snapshot=None,
            )

    class _Captures:
        async def insert(self, **kwargs):
            return SimpleNamespace(id=uuid.uuid4(), context_snapshot=kwargs.get("context_snapshot"))

        async def get_for_chat(self, _chat_id, capture_id):
            return SimpleNamespace(
                id=capture_id,
                chat_id=chat_id,
                title="Audio transcript",
                status="running",
                parse_job_id="job_test",
                host_attachment_id=inserted_host_id,
                input_message_id=uuid.uuid4(),
                output_annotation_id=uuid.uuid4(),
                error_code=None,
                error_message=None,
                context_snapshot={"parts": []},
                created_at=None,
                updated_at=None,
            )

        async def list_parts(self, _capture_id):
            return [
                SimpleNamespace(
                    id=part_id,
                    filename="clip.m4a",
                    mime_type="audio/mp4",
                    size_bytes=1024,
                )
            ]

    class _Messages:
        async def insert(self, **kwargs):
            return SimpleNamespace(id=uuid.uuid4())

    class _Annotations:
        async def insert(self, **kwargs):
            return SimpleNamespace(id=uuid.uuid4())

    class _Session:
        async def flush(self) -> None:
            return None

        async def commit(self) -> None:
            return None

        async def refresh(self, _obj) -> None:
            return None

    service = AudioCaptureService(_Session())  # type: ignore[arg-type]
    service._attachments = _Attachments(_Session())  # type: ignore[assignment]
    service._captures = _Captures()  # type: ignore[assignment]
    service._messages = _Messages()  # type: ignore[assignment]
    service._annotations = _Annotations()  # type: ignore[assignment]

    result = await service.submit_capture_from_blob_parts(
        chat,  # type: ignore[arg-type]
        title=None,
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

    assert blob_check_called is True
    assert result["status"] == "running"
