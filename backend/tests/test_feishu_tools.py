import pytest

from app.platform.integrations.feishu.client import FeishuApiError
from app.platform.integrations.feishu.context import init_feishu_context, reset_feishu_context
from app.platform.integrations.feishu.tools import (
    feishu_get_doc_content_tool,
    feishu_list_calendar_events_tool,
    feishu_list_chats_tool,
)


@pytest.fixture(autouse=True)
def _reset_feishu_context():
    reset_feishu_context()
    yield
    reset_feishu_context()


def test_feishu_tools_require_connection():
    init_feishu_context(access_token=None)
    result = feishu_list_chats_tool(page_size=5)
    assert result["status"] == "error"
    assert result["code"] == "not_connected"


def test_feishu_list_chats(monkeypatch):
    init_feishu_context(access_token="token", api_base="https://open.feishu.cn")
    monkeypatch.setattr(
        "app.platform.integrations.feishu.tools.list_chats",
        lambda token, api_base, page_size: [{"chat_id": "oc_1", "name": "Team"}],
    )
    result = feishu_list_chats_tool(page_size=5)
    assert result["status"] == "ok"
    assert result["chats"][0]["chat_id"] == "oc_1"


def test_feishu_get_doc_content(monkeypatch):
    init_feishu_context(access_token="token", api_base="https://open.feishu.cn")
    monkeypatch.setattr(
        "app.platform.integrations.feishu.tools.get_doc_raw_content",
        lambda token, api_base, document_id: {"document_id": document_id, "content": "hello"},
    )
    result = feishu_get_doc_content_tool(
        document_id_or_url="https://example.feishu.cn/docx/doxcnTest123",
    )
    assert result["status"] == "ok"
    assert result["document_id"] == "doxcnTest123"


def test_feishu_list_calendar_events(monkeypatch):
    init_feishu_context(access_token="token", api_base="https://open.feishu.cn")
    monkeypatch.setattr(
        "app.platform.integrations.feishu.tools.list_calendar_events",
        lambda token, api_base, days_ahead, page_size: {
            "calendar_id": "cal_1",
            "calendar_name": "Primary",
            "count": 1,
            "events": [{"event_id": "evt_1", "summary": "Standup"}],
        },
    )
    result = feishu_list_calendar_events_tool(days_ahead=7, page_size=10)
    assert result["status"] == "ok"
    assert result["events"][0]["summary"] == "Standup"


def test_feishu_client_invalid_document():
    from app.platform.integrations.feishu.client import get_doc_raw_content

    with pytest.raises(FeishuApiError) as exc:
        get_doc_raw_content("token", api_base="https://open.feishu.cn", document_id="  ")
    assert exc.value.code == "invalid_document_id"
