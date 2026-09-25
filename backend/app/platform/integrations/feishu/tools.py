"""Builtin Feishu Open Platform tools (read-only pilot)."""

from __future__ import annotations

from typing import Annotated, Any

from agent_framework import tool

from app.platform.integrations.feishu.client import (
    FeishuApiError,
    get_doc_raw_content,
    list_calendar_events,
    list_chats,
    list_messages,
)
from app.platform.integrations.feishu.context import require_feishu_context
from app.platform.integrations.providers.feishu import FEISHU_PROVIDER_ID, feishu_document_id_from_url

FEISHU_TOOL_NAMES = frozenset(
    {
        "feishu_list_chats",
        "feishu_list_messages",
        "feishu_get_doc_content",
        "feishu_list_calendar_events",
    }
)

_CONNECT_HINT = (
    f"Connect Feishu in Settings → Integrations ({FEISHU_PROVIDER_ID}) before using Feishu tools."
)


def _error_payload(code: str, message: str) -> dict[str, Any]:
    return {"status": "error", "code": code, "message": message}


def _require_access_token() -> tuple[str, str]:
    ctx = require_feishu_context()
    if not ctx.access_token:
        raise FeishuApiError("not_connected", _CONNECT_HINT)
    return ctx.access_token, ctx.api_base


@tool(
    name="feishu_list_chats",
    description="List Feishu chats (groups and p2p) available to the connected user.",
)
def feishu_list_chats_tool(
    page_size: Annotated[int, "Max chats to return (1-50)."] = 20,
) -> dict[str, Any]:
    try:
        token, api_base = _require_access_token()
        chats = list_chats(token, api_base=api_base, page_size=page_size)
        return {"status": "ok", "count": len(chats), "chats": chats}
    except FeishuApiError as exc:
        return _error_payload(exc.code, exc.message)
    except RuntimeError as exc:
        return _error_payload("no_context", str(exc))


@tool(
    name="feishu_list_messages",
    description="List recent messages in a Feishu chat. Use feishu_list_chats to discover chat_id.",
)
def feishu_list_messages_tool(
    chat_id: Annotated[str, "Feishu chat_id from feishu_list_chats."],
    page_size: Annotated[int, "Max messages to return (1-50)."] = 20,
) -> dict[str, Any]:
    try:
        token, api_base = _require_access_token()
        messages = list_messages(token, api_base=api_base, chat_id=chat_id, page_size=page_size)
        return {"status": "ok", "chat_id": chat_id.strip(), "count": len(messages), "messages": messages}
    except FeishuApiError as exc:
        return _error_payload(exc.code, exc.message)
    except RuntimeError as exc:
        return _error_payload("no_context", str(exc))


@tool(
    name="feishu_get_doc_content",
    description=(
        "Read plain-text content of a Feishu docx document by document_id or docx URL."
    ),
)
def feishu_get_doc_content_tool(
    document_id_or_url: Annotated[str, "Feishu docx document_id or full docx URL."],
) -> dict[str, Any]:
    try:
        token, api_base = _require_access_token()
        document_id = feishu_document_id_from_url(document_id_or_url) or document_id_or_url.strip()
        payload = get_doc_raw_content(token, api_base=api_base, document_id=document_id)
        return {"status": "ok", **payload}
    except FeishuApiError as exc:
        return _error_payload(exc.code, exc.message)
    except RuntimeError as exc:
        return _error_payload("no_context", str(exc))


@tool(
    name="feishu_list_calendar_events",
    description="List upcoming events from the connected user's primary Feishu calendar.",
)
def feishu_list_calendar_events_tool(
    days_ahead: Annotated[int, "How many days ahead to include (1-30)."] = 7,
    page_size: Annotated[int, "Max events to return (1-50)."] = 20,
) -> dict[str, Any]:
    try:
        token, api_base = _require_access_token()
        payload = list_calendar_events(
            token,
            api_base=api_base,
            days_ahead=days_ahead,
            page_size=page_size,
        )
        return {"status": "ok", **payload}
    except FeishuApiError as exc:
        return _error_payload(exc.code, exc.message)
    except RuntimeError as exc:
        return _error_payload("no_context", str(exc))


FEISHU_BUILTIN_TOOLS: dict[str, Any] = {
    "feishu_list_chats": feishu_list_chats_tool,
    "feishu_list_messages": feishu_list_messages_tool,
    "feishu_get_doc_content": feishu_get_doc_content_tool,
    "feishu_list_calendar_events": feishu_list_calendar_events_tool,
}
