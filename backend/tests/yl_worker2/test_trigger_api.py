"""Webhook API and message persistence tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.models import DEV_USER_ID
from app.main import app
from app.platform.current_user import get_current_user_id
from app.yl_worker2.triggers.handler import _persist_trigger_user_message


@pytest.fixture
def trigger_client():
    app.dependency_overrides[get_current_user_id] = lambda: DEV_USER_ID
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


"""Webhook API and message persistence tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.models import DEV_USER_ID
from app.main import app
from app.platform.current_user import get_current_user_id
from app.yl_worker2.triggers.handler import _persist_trigger_user_message
from app.yl_worker2.triggers.schemas import YlWorker2TriggerResponse


@pytest.fixture
def trigger_client():
    app.dependency_overrides[get_current_user_id] = lambda: DEV_USER_ID
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_trigger_default_auto_run_invokes_agent(trigger_client):
    with patch(
        "app.api.routes.yl_worker2_triggers.handle_yl_worker2_trigger",
        new_callable=AsyncMock,
        return_value=YlWorker2TriggerResponse(
            chat_id="00000000-0000-0000-0000-000000000001",
            agent_slug="yl-worker2",
            initial_message="【外系统事件】大客户追加订单",
            status="session_created_and_run_completed",
        ),
    ) as handler_mock:
        response = trigger_client.post(
            "/api/v1/agents/yl-worker2/triggers",
            json={
                "event_type": "large_order_added",
                "product_code": "MOCK_YLP001",
                "adjust_date": "2026-06-30",
                "site_code": "MOCK_WH_S07",
                "detail": {"order_delta": 2800},
            },
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["status"] == "session_created_and_run_completed"
    handler_mock.assert_awaited_once()
    assert handler_mock.await_args.kwargs.get("auto_run") is True


def test_trigger_auto_run_false_query_param(trigger_client):
    with patch(
        "app.api.routes.yl_worker2_triggers.handle_yl_worker2_trigger",
        new_callable=AsyncMock,
        return_value=YlWorker2TriggerResponse(
            chat_id="00000000-0000-0000-0000-000000000002",
            agent_slug="yl-worker2",
            initial_message="【外系统事件】基地仓入库延期",
            status="session_created",
        ),
    ) as handler_mock:
        response = trigger_client.post(
            "/api/v1/agents/yl-worker2/triggers?auto_run=false",
            json={
                "event_type": "base_inbound_delay",
                "product_code": "MOCK_YLP001",
                "adjust_date": "2026-06-30",
                "site_code": "MOCK_WH_B02",
                "detail": {"from_available_after": 3200},
            },
        )
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "session_created"
    assert handler_mock.await_args.kwargs.get("auto_run") is False


@pytest.mark.asyncio
async def test_persist_trigger_user_message_inserts_user_row():
    db = MagicMock()
    with patch(
        "app.yl_worker2.triggers.handler.MessageRepository"
    ) as repo_cls:
        repo = repo_cls.return_value
        repo.insert = AsyncMock()
        await _persist_trigger_user_message(db, __import__("uuid").uuid4(), "测试消息")
        repo.insert.assert_awaited_once()
        kwargs = repo.insert.await_args.kwargs
        assert kwargs["role"] == "user"
        assert kwargs["content"] == "测试消息"
        assert kwargs["metadata"]["source"] == "yl_worker2_trigger"
