import uuid

import pytest

from app.platform.attachments.visibility_constants import VISIBILITY_INLINED
from app.platform.attachments.run_state import AttachmentRecord, init_attachment_run_state, reset_attachment_run_state
from app.platform.attachments.tools.pull_tools import analyze_image_tool, inline_attachment_tool


CHAT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ATTACHMENT_ID = "22222222-2222-2222-2222-222222222222"


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    reset_attachment_run_state()
    yield
    reset_attachment_run_state()


def _record() -> AttachmentRecord:
    return AttachmentRecord(
        attachment_id=uuid.UUID(ATTACHMENT_ID),
        chat_id=CHAT_ID,
        filename="chart.png",
        mime_type="image/png",
        provider="unify_lite",
        provider_file_id=f"inline:{ATTACHMENT_ID}",
        size_bytes=64,
    )


@pytest.mark.asyncio
async def test_analyze_image_blocked_when_already_inlined() -> None:
    state = init_attachment_run_state(chat_id=CHAT_ID, attachments=[_record()])
    state.turn_visibility[ATTACHMENT_ID] = VISIBILITY_INLINED
    state.turn_mentioned_ids = [ATTACHMENT_ID]

    result = await analyze_image_tool(ATTACHMENT_ID)
    assert result["status"] == "error"
    assert result.get("recovery") == "answer_from_context"
    assert "Answer directly" in result["message"]
    assert "inlined_this_turn" in result["message"]


@pytest.mark.asyncio
async def test_inline_attachment_idempotent_same_turn() -> None:
    state = init_attachment_run_state(chat_id=CHAT_ID, attachments=[_record()])
    state.turn_mentioned_ids = [ATTACHMENT_ID]
    state.turn_visibility[ATTACHMENT_ID] = "not_inlined"

    first = await inline_attachment_tool(ATTACHMENT_ID)
    assert first["status"] == "ok"
    second = await inline_attachment_tool(ATTACHMENT_ID)
    assert second["status"] == "ok"
    assert second.get("cached") is True
