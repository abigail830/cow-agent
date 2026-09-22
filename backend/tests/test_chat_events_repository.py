import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.repositories.chat_events import ChatEventRepository


@pytest.mark.asyncio
async def test_insert_many_assigns_sequences():
    chat_id = uuid.uuid4()
    session = AsyncMock()
    session.flush = AsyncMock()

    seq_result = MagicMock()
    seq_result.scalar_one.return_value = 2
    session.execute = AsyncMock(return_value=seq_result)

    repo = ChatEventRepository(session)
    saved = await repo.insert_many(
        chat_id,
        [
            {"role": "assistant", "message_type": "text", "content": "hello"},
            {"role": "user", "message_type": "text", "content": "hi"},
        ],
    )

    assert len(saved) == 2
    assert saved[0].sequence == 3
    assert saved[1].sequence == 4
    assert saved[0].payload["role"] == "assistant"
