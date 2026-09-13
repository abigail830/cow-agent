import uuid
from unittest.mock import AsyncMock

import pytest

from app.platform.attachments.run_state import AttachmentRecord, init_attachment_run_state, reset_attachment_run_state
from app.platform.attachments.services.map import AttachmentMapService, map_cache_key
from app.platform.attachments.tools.pull_tools import map_attachment_tool

CHAT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
DOC_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")
IMG_ID = uuid.UUID("44444444-4444-4444-4444-444444444444")


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    yield
    reset_attachment_run_state()


@pytest.fixture
def _run_state() -> None:
    init_attachment_run_state(
        chat_id=CHAT_ID,
        attachments=[
            AttachmentRecord(
                attachment_id=DOC_ID,
                chat_id=CHAT_ID,
                filename="report.docx",
                mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                provider="unify_lite",
                provider_file_id=f"inline:{DOC_ID}",
                size_bytes=100,
                content_hash="sha256:abc",
                gist="report",
            ),
            AttachmentRecord(
                attachment_id=IMG_ID,
                chat_id=CHAT_ID,
                filename="chart.png",
                mime_type="image/png",
                provider="unify_lite",
                provider_file_id=f"inline:{IMG_ID}",
                size_bytes=50,
                content_hash="sha256:img",
                gist="chart",
            ),
        ],
    )


@pytest.mark.asyncio
async def test_map_document_returns_summary(monkeypatch: pytest.MonkeyPatch, _run_state: None) -> None:
    monkeypatch.setattr(
        "app.platform.attachments.services.map.load_inline_attachment",
        lambda _chat_id, _blob_id: b"doc-bytes",
    )
    monkeypatch.setattr(
        "app.platform.attachments.services.read.extract_bytes",
        lambda **kwargs: ("Quarter revenue grew 12 percent.", [], 0),
    )
    monkeypatch.setattr(
        "app.platform.attachments.services.map.ephemeral_text_run",
        AsyncMock(return_value="The report discusses Q1 revenue growth of 12%."),
    )
    service = AttachmentMapService()
    result = await service.map_one(str(DOC_ID), focus="revenue")
    assert result["status"] == "ok"
    assert "12" in str(result["summary"])
    assert "content" not in result
    assert result.get("content_hash") == "sha256:abc"


@pytest.mark.asyncio
async def test_map_cache_hit_skips_second_worker(
    monkeypatch: pytest.MonkeyPatch,
    _run_state: None,
) -> None:
    monkeypatch.setattr(
        "app.platform.attachments.services.map.load_inline_attachment",
        lambda _chat_id, _blob_id: b"hello doc",
    )
    monkeypatch.setattr(
        "app.platform.attachments.services.read.extract_bytes",
        lambda **kwargs: ("hello doc", [], 0),
    )
    mock_run = AsyncMock(return_value="Cached summary text.")
    monkeypatch.setattr("app.platform.attachments.services.map.ephemeral_text_run", mock_run)
    service = AttachmentMapService()
    first = await service.map_one(str(DOC_ID))
    second = await service.map_one(str(DOC_ID))
    assert first["status"] == "ok"
    assert second.get("cached") is True
    assert mock_run.await_count == 1


@pytest.mark.asyncio
async def test_map_image_uses_vision(monkeypatch: pytest.MonkeyPatch, _run_state: None) -> None:
    monkeypatch.setattr(
        "app.platform.attachments.services.map.load_inline_attachment",
        lambda _chat_id, _blob_id: b"\x89PNG",
    )

    class _FakeVision:
        async def describe(self, **kwargs: object) -> dict:
            return {"status": "ok", "summary": "A line chart.", "confidence": "ok"}

    service = AttachmentMapService(vision_service=_FakeVision())
    result = await service.map_one(str(IMG_ID))
    assert result["summary"] == "A line chart."


@pytest.mark.asyncio
async def test_map_attachment_tool_no_full_text_in_payload(
    monkeypatch: pytest.MonkeyPatch,
    _run_state: None,
) -> None:
    monkeypatch.setattr(
        "app.platform.attachments.services.map.load_inline_attachment",
        lambda _chat_id, _blob_id: b"x" * 5000,
    )
    monkeypatch.setattr(
        "app.platform.attachments.services.read.extract_bytes",
        lambda **kwargs: ("x" * 5000, [], 0),
    )
    monkeypatch.setattr(
        "app.platform.attachments.services.map.ephemeral_text_run",
        AsyncMock(return_value="Short summary."),
    )
    result = await map_attachment_tool(str(DOC_ID))
    assert result["status"] == "ok"
    assert len(str(result.get("summary") or "")) < 500
    assert "content" not in result


def test_map_cache_key_includes_focus() -> None:
    assert map_cache_key("id1", "hash1", None) != map_cache_key("id1", "hash1", "违约条款")
