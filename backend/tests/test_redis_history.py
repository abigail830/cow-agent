import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.platform.memory.redis_history import (
    APPLICATION_ID,
    HISTORY_SOURCE_ID,
    RedisHistoryUnavailableError,
    create_history_provider,
    create_redis_history_provider,
)


def test_create_redis_history_provider_scoped_keys():
    chat_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    with patch("app.platform.memory.redis_history.get_redis", return_value=MagicMock()):
        provider = create_redis_history_provider(chat_id=chat_id, agent_id=agent_id)
    assert provider.source_id == HISTORY_SOURCE_ID
    assert provider.application_id == APPLICATION_ID
    assert provider.agent_id == str(agent_id)
    assert provider.store_inputs is True
    assert provider.store_outputs is True


@pytest.mark.asyncio
async def test_create_history_provider_uses_redis_when_available():
    chat_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    with (
        patch(
            "app.platform.memory.redis_history.check_redis_connection",
            AsyncMock(return_value=True),
        ),
        patch("app.platform.memory.redis_history.get_redis", return_value=MagicMock()),
    ):
        provider = await create_history_provider(chat_id=chat_id, agent_id=agent_id)
    assert provider.source_id == HISTORY_SOURCE_ID
    assert provider.__class__.__name__ == "RedisHistoryProvider"


@pytest.mark.asyncio
async def test_create_history_provider_falls_back_locally_when_redis_down():
    chat_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    with (
        patch(
            "app.platform.memory.redis_history.check_redis_connection",
            AsyncMock(return_value=False),
        ),
        patch("app.platform.memory.redis_history.IS_VERCEL", False),
        patch("app.platform.memory.redis_history.get_settings") as mock_settings,
    ):
        mock_settings.return_value.redis_history_fallback = "none"
        mock_settings.return_value.redis_history_required = False
        provider = await create_history_provider(chat_id=chat_id, agent_id=agent_id)
    assert provider.__class__.__name__ == "InMemoryHistoryProvider"


@pytest.mark.asyncio
async def test_create_history_provider_raises_on_vercel_when_redis_down():
    chat_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    with (
        patch(
            "app.platform.memory.redis_history.check_redis_connection",
            AsyncMock(return_value=False),
        ),
        patch("app.platform.memory.redis_history.IS_VERCEL", True),
        patch("app.platform.memory.redis_history.get_settings") as mock_settings,
    ):
        mock_settings.return_value.redis_history_fallback = "none"
        mock_settings.return_value.redis_history_required = False
        with pytest.raises(RedisHistoryUnavailableError):
            await create_history_provider(chat_id=chat_id, agent_id=agent_id)
