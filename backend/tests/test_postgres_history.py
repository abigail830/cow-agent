import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from agent_framework import Content, Message

from app.platform.memory.memory_config import MemoryConfig, HistoryLoadConfig
from app.platform.memory.postgres_history import PostgresHistoryProvider


@pytest.mark.asyncio
async def test_postgres_history_load_window_tail():
    chat_id = uuid.uuid4()
    tail_rows = [
        MagicMock(body=Message(role="user", contents=[Content.from_text("m3")]).to_dict()),
        MagicMock(body=Message(role="user", contents=[Content.from_text("m4")]).to_dict()),
    ]

    provider = PostgresHistoryProvider(
        MagicMock(),
        chat_id=chat_id,
        memory_config=MemoryConfig(history_load=HistoryLoadConfig(max_messages=2)),
    )
    provider._messages = MagicMock()
    provider._messages.list_by_chat = AsyncMock(return_value=tail_rows)

    messages = await provider.get_messages(str(chat_id))
    assert len(messages) == 2
    provider._messages.list_by_chat.assert_awaited_once_with(chat_id, tail=2)


@pytest.mark.asyncio
async def test_postgres_history_unlimited_when_max_zero():
    chat_id = uuid.uuid4()

    provider = PostgresHistoryProvider(
        MagicMock(),
        chat_id=chat_id,
        memory_config=MemoryConfig(history_load=HistoryLoadConfig(max_messages=0)),
    )
    provider._messages = MagicMock()
    provider._messages.list_by_chat = AsyncMock(return_value=[])

    await provider.get_messages(str(chat_id))
    provider._messages.list_by_chat.assert_awaited_once_with(chat_id, tail=None)
