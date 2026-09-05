"""Bulk message insert tests."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.repositories.messages import MessageRepository


@pytest.mark.asyncio
async def test_insert_many_batches_single_flush():
    chat_id = uuid.uuid4()
    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalar_one.return_value = 4
    session.execute = AsyncMock(return_value=result)

    repo = MessageRepository(session)
    rows = [
        {"role": "assistant", "message_type": "text", "content": "Hello", "metadata": {}},
        {"role": "assistant", "message_type": "tool_call", "content": None, "metadata": {"call_id": "c1"}},
    ]

    saved = await repo.insert_many(chat_id, rows)

    assert len(saved) == 2
    assert saved[0].sequence == 5
    assert saved[1].sequence == 6
    assert session.add.call_count == 2
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_insert_many_empty_returns_without_flush():
    session = AsyncMock()
    repo = MessageRepository(session)

    saved = await repo.insert_many(uuid.uuid4(), [])

    assert saved == []
    session.flush.assert_not_awaited()
