import uuid

import pytest

from app.platform.attachments.run_state import AttachmentRecord, init_attachment_run_state, reset_attachment_run_state
from app.platform.attachments.tools.pull_tools import read_attachment_tool, search_attachments_tool


CHAT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ATTACHMENT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


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
                attachment_id=ATTACHMENT_ID,
                chat_id=CHAT_ID,
                filename="notes.txt",
                mime_type="text/plain",
                provider="unify_lite",
                provider_file_id=f"inline:{ATTACHMENT_ID}",
                size_bytes=12,
                gist="meeting notes",
            )
        ],
    )


def test_read_attachment_rejects_foreign_chat(monkeypatch: pytest.MonkeyPatch, _run_state: None) -> None:
    other_chat = uuid.UUID("33333333-3333-3333-3333-333333333333")
    init_attachment_run_state(
        chat_id=other_chat,
        attachments=[
            AttachmentRecord(
                attachment_id=ATTACHMENT_ID,
                chat_id=CHAT_ID,
                filename="notes.txt",
                mime_type="text/plain",
                provider="unify_lite",
                provider_file_id=f"inline:{ATTACHMENT_ID}",
                size_bytes=12,
            )
        ],
    )
    result = read_attachment_tool(str(ATTACHMENT_ID))
    assert result["status"] == "error"


def test_read_attachment_returns_extracted_text(monkeypatch: pytest.MonkeyPatch, _run_state: None) -> None:
    monkeypatch.setattr(
        "app.platform.attachments.tools.pull_tools.load_inline_attachment",
        lambda _chat_id, _attachment_id: b"hello attachment world",
    )
    result = read_attachment_tool(str(ATTACHMENT_ID))
    assert result["status"] == "ok"
    assert "hello attachment world" in result["content"]

    cached = read_attachment_tool(str(ATTACHMENT_ID))
    assert cached.get("cached") is True


def test_search_attachments_matches_gist(_run_state: None) -> None:
    result = search_attachments_tool("meeting")
    assert result["status"] == "ok"
    assert result["count"] == 1
