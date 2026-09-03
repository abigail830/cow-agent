"""Handler integration: auto_run branches."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models import DEV_USER_ID
from app.yl_worker2.triggers.handler import handle_yl_worker2_trigger
from app.yl_worker2.triggers.schemas import YlWorker2TriggerPayload


@pytest.mark.asyncio
async def test_handle_trigger_auto_run_false_persists_only():
    payload = YlWorker2TriggerPayload(
        event_type="base_inbound_delay",
        product_code="MOCK_YLP001",
        adjust_date="2026-06-30",
        site_code="MOCK_WH_B02",
        detail={"from_available_after": 3200},
    )
    agent = MagicMock()
    db = MagicMock()
    db.get = AsyncMock(return_value=agent)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    with (
        patch("app.yl_worker2.triggers.handler._persist_trigger_user_message", new_callable=AsyncMock) as persist,
        patch("app.yl_worker2.triggers.handler.ChatRunService") as run_cls,
    ):
        result = await handle_yl_worker2_trigger(
            db,
            payload,
            user_id=DEV_USER_ID,
            auto_run=False,
        )

    persist.assert_awaited_once()
    run_cls.assert_not_called()
    assert result.status == "session_created"
    assert result.agent_slug == "yl-worker2"


@pytest.mark.asyncio
async def test_handle_trigger_auto_run_true_runs_agent():
    payload = YlWorker2TriggerPayload(
        event_type="large_order_added",
        product_code="MOCK_YLP001",
        adjust_date="2026-06-30",
        site_code="MOCK_WH_S07",
        detail={"order_delta": 2800},
    )
    agent = MagicMock()
    db = MagicMock()
    db.get = AsyncMock(return_value=agent)
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()

    with patch("app.yl_worker2.triggers.handler.ChatRunService") as run_cls:
        run_cls.return_value.run_message = AsyncMock(return_value="ok")
        result = await handle_yl_worker2_trigger(
            db,
            payload,
            user_id=DEV_USER_ID,
            auto_run=True,
        )

    run_cls.return_value.run_message.assert_awaited_once()
    assert result.status == "session_created_and_run_completed"
