from __future__ import annotations

import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.platform.parse_pipeline.inline_runner import (
    _ensure_original_on_disk,
    _file_path_from_url,
    run_inline_job,
)


def test_file_path_from_url() -> None:
    path = _file_path_from_url(Path("/tmp/a.docx").as_uri())
    assert path == Path("/tmp/a.docx")


def test_ensure_original_on_disk_materializes_missing_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    original = tmp_path / str(chat_id) / str(attachment_id)
    payload = {
        "source": {"tenant_id": str(chat_id), "source_id": str(attachment_id)},
        "storage": {"read": {"url": original.as_uri()}},
    }

    def fake_load(_chat: uuid.UUID, _att: uuid.UUID) -> bytes:
        return b"docx-bytes"

    monkeypatch.setattr(
        "app.platform.attachments.storage.load_inline_attachment",
        fake_load,
    )
    _ensure_original_on_disk(payload)
    assert original.read_bytes() == b"docx-bytes"


@pytest.mark.asyncio
async def test_run_inline_job_invokes_subprocess(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    parsed_dir = tmp_path / "parsed"
    parsed_dir.mkdir()
    original = tmp_path / "original.docx"
    original.write_bytes(b"x")
    payload = {
        "job_id": "job_test",
        "pipeline_id": "text_standard",
        "source": {"tenant_id": str(chat_id), "source_id": str(attachment_id)},
        "storage": {
            "read": {"url": original.as_uri()},
            "write": {
                "content_md": {"url": (parsed_dir / "content.md").as_uri(), "method": "PUT"},
                "meta_json": {"url": (parsed_dir / "meta.json").as_uri(), "method": "PUT"},
            },
        },
    }
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):  # type: ignore[no-untyped-def]
        calls.append(cmd)
        parsed_dir.joinpath("meta.json").write_text('{"parse_status":"ready"}', encoding="utf-8")
        parsed_dir.joinpath("content.md").write_text("# ok\n", encoding="utf-8")
        class R:
            returncode = 0
            stdout = ""
            stderr = ""

        return R()

    monkeypatch.setattr("app.platform.parse_pipeline.inline_runner.subprocess.run", fake_run)
    await run_inline_job(payload)
    assert calls
    assert "run-job" in calls[0]
