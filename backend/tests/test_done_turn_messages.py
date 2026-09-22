import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models import ChatEvent
from app.platform.chat.event_projection import event_to_dict
from app.platform.chat.run_service import ChatRunService


def test_event_to_dict_matches_api_shape():
    chat_id = uuid.uuid4()
    event = ChatEvent(
        id=uuid.uuid4(),
        chat_id=chat_id,
        sequence=1,
        event_type="message",
        payload={
            "role": "user",
            "message_type": "text",
            "content": "hello",
            "metadata": {"k": "v"},
            "parent_id": None,
        },
        created_at=datetime.now(timezone.utc),
    )
    out = event_to_dict(event)
    assert out["chat_id"] == str(chat_id)
    assert out["role"] == "user"
    assert out["message_type"] == "text"
    assert out["metadata"] == {"k": "v"}


@pytest.mark.asyncio
async def test_list_turn_messages_since_uses_repository_filter():
    chat_id = uuid.uuid4()
    row = ChatEvent(
        id=uuid.uuid4(),
        chat_id=chat_id,
        sequence=5,
        event_type="message",
        payload={"role": "user", "message_type": "text", "content": "x", "metadata": {}},
    )
    service = ChatRunService(AsyncMock())
    service._events = AsyncMock()
    service._events.list_by_chat_since = AsyncMock(return_value=[row])

    result = await service._list_turn_messages_since(chat_id, 5)

    service._events.list_by_chat_since.assert_awaited_once_with(chat_id, 5)
    assert result == [event_to_dict(row)]
