from __future__ import annotations

import json
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.platform.audio_capture.webhook import (
    _capture_job_status,
    maybe_finalize_capture_after_parsed_artifact,
    sync_capture_from_parse_webhook,
)
from app.platform.parse_pipeline.webhook import apply_webhook_event


def test_capture_job_status_maps_parse_status() -> None:
    assert _capture_job_status("ready") == ("ready", "ready")
    assert _capture_job_status("failed") == ("failed", "failed")
    assert _capture_job_status("running") == ("running", "running")


@pytest.mark.asyncio
async def test_sync_capture_marks_annotation_ready() -> None:
    attachment_id = uuid.uuid4()
    capture_id = uuid.uuid4()
    annotation_id = uuid.uuid4()
    capture = SimpleNamespace(
        id=capture_id,
        chat_id=uuid.uuid4(),
        title="Audio transcript",
        output_annotation_id=annotation_id,
    )
    annotation = SimpleNamespace(display={"title": "Audio transcript"})
    session = AsyncMock()
    session.get = AsyncMock(return_value=annotation)

    with patch(
        "app.platform.audio_capture.webhook.AudioCaptureRepository",
    ) as repo_cls:
        repo = repo_cls.return_value
        repo.get_by_host_attachment = AsyncMock(return_value=capture)
        repo.update_status = AsyncMock()
        await sync_capture_from_parse_webhook(
            session,
            attachment_id=attachment_id,
            parse_status="ready",
        )

    repo.update_status.assert_awaited_once()
    assert annotation.display["spec"]["job_status"] == "ready"
    assert annotation.display["spec"]["download_url"]


@pytest.mark.asyncio
async def test_apply_webhook_trusts_artifacts_ready_flag() -> None:
    attachment_id = uuid.uuid4()
    chat_id = uuid.uuid4()
    run_row = SimpleNamespace(job_id="job_test", attachment_id=attachment_id, status="running")
    attachment = SimpleNamespace(
        id=attachment_id,
        chat_id=chat_id,
        parse_status="running",
        parse_pipeline_id="audio_transcription_standard",
        parse_job_id="job_test",
        parse_error_message=None,
        parsed_artifact_manifest=None,
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=attachment)

    payload = {
        "event": "job.completed",
        "job_id": "job_test",
        "status": "succeeded",
        "artifacts": {"ready": True, "content_md": True, "meta_json": True},
        "progress": {"message": "done"},
        "stages": [],
    }
    body = json.dumps(payload).encode("utf-8")

    with (
        patch("app.platform.parse_pipeline.webhook.ParseJobRepository") as jobs_cls,
        patch("app.platform.parse_pipeline.webhook.DocstoreRepository") as docstore_cls,
        patch("app.platform.audio_capture.webhook.sync_capture_from_parse_webhook", AsyncMock()) as sync_capture,
        patch("app.platform.parse_pipeline.webhook.publish_attachment_parse_updated"),
    ):
        jobs = jobs_cls.return_value
        jobs.record_event = AsyncMock(return_value=True)
        jobs.update_run_status = AsyncMock()
        docstore = docstore_cls.return_value
        docstore.apply_parse_webhook = AsyncMock(return_value=attachment)

        result = await apply_webhook_event(
            session,
            event_id="evt-1",
            body=body,
            run_row=run_row,
        )

    assert result is not None
    docstore.apply_parse_webhook.assert_awaited_once()
    assert docstore.apply_parse_webhook.await_args.kwargs["status"] == "ready"
    sync_capture.assert_awaited_once()
    assert sync_capture.await_args.kwargs["parse_status"] == "ready"


@pytest.mark.asyncio
async def test_maybe_finalize_capture_after_meta_json() -> None:
    attachment_id = uuid.uuid4()
    attachment = SimpleNamespace(
        id=attachment_id,
        attachment_role="transcript_host",
        parsed_artifact_manifest={"content_md": {}, "meta_json": {}},
    )
    session = AsyncMock()
    session.get = AsyncMock(return_value=attachment)

    with (
        patch("app.platform.audio_capture.webhook.DocstoreRepository") as docstore_cls,
        patch("app.platform.audio_capture.webhook.sync_capture_from_parse_webhook", AsyncMock()) as sync_capture,
        patch(
            "app.platform.audio_capture.webhook.parsed_artifact_in_manifest",
            side_effect=lambda manifest, key: key in (manifest or {}),
        ),
    ):
        docstore = docstore_cls.return_value
        docstore.apply_parse_webhook = AsyncMock()
        await maybe_finalize_capture_after_parsed_artifact(
            session,
            attachment_id=attachment_id,
            artifact_key="meta_json",
        )

    docstore.apply_parse_webhook.assert_awaited_once()
    sync_capture.assert_awaited_once()
