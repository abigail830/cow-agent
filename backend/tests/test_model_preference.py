import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.platform.llm.model_preference import get_model_preference, set_model_preference


@pytest.mark.asyncio
async def test_get_model_preference_reads_from_repository() -> None:
    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    db = AsyncMock()
    with patch(
        "app.platform.llm.model_preference.ModelPreferenceRepository.get",
        new=AsyncMock(return_value="deepseek-flash"),
    ) as get_mock:
        result = await get_model_preference(db, user_id, agent_id)
    assert result == "deepseek-flash"
    get_mock.assert_awaited_once_with(user_id, agent_id)


@pytest.mark.asyncio
async def test_set_model_preference_writes_via_repository() -> None:
    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    db = AsyncMock()
    with patch(
        "app.platform.llm.model_preference.ModelPreferenceRepository.upsert",
        new=AsyncMock(),
    ) as upsert_mock:
        await set_model_preference(db, user_id, agent_id, "deepseek-flash")
    upsert_mock.assert_awaited_once_with(user_id, agent_id, "deepseek-flash")
