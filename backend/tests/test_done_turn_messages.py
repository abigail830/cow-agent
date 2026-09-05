"""P2-1: done SSE carries persisted turn rows."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.platform.chat.run_service import ChatRunService, message_row_to_out


def test_message_row_to_out_matches_api_shape():
    chat_id = uuid.uuid4()
    row = MagicMock()
    row.id = uuid.uuid4()
    row.chat_id = chat_id
    row.role = "assistant"
    row.message_type = "text"
    row.content = "hello"
    row.message_metadata = {"source": "test"}
    row.parent_id = None
    row.sequence = 3
    row.created_at = datetime(2026, 1, 2, tzinfo=timezone.utc)

    out = message_row_to_out(row)

    assert out == {
        "id": str(row.id),
        "chat_id": str(chat_id),
        "role": "assistant",
        "message_type": "text",
        "content": "hello",
        "metadata": {"source": "test"},
        "parent_id": None,
        "sequence": 3,
        "created_at": row.created_at.isoformat(),
    }


@pytest.mark.asyncio
async def test_list_turn_messages_since_uses_repository_filter():
    chat_id = uuid.uuid4()
    db = AsyncMock()
    service = ChatRunService(db)

    row = MagicMock()
    row.id = uuid.uuid4()
    row.chat_id = chat_id
    row.role = "user"
    row.message_type = "text"
    row.content = "hi"
    row.message_metadata = {}
    row.parent_id = None
    row.sequence = 5
    row.created_at = None

    service._messages = AsyncMock()
    service._messages.list_by_chat_since = AsyncMock(return_value=[row])

    result = await service._list_turn_messages_since(chat_id, 5)

    service._messages.list_by_chat_since.assert_awaited_once_with(chat_id, 5)
    assert result == [message_row_to_out(row)]
