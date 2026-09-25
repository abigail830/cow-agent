"""Sync Feishu Open Platform client helpers."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

import httpx

_TIMEOUT_SECONDS = 30.0


class FeishuApiError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _headers(access_token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }


def _request(
    access_token: str,
    method: str,
    api_base: str,
    path: str,
    *,
    params: dict[str, str | int] | None = None,
) -> dict[str, Any]:
    url = f"{api_base.rstrip('/')}{path}"
    with httpx.Client(timeout=_TIMEOUT_SECONDS) as client:
        response = client.request(method, url, headers=_headers(access_token), params=params)
    try:
        payload = response.json() if response.content else {}
    except ValueError as exc:
        raise FeishuApiError("invalid_json", response.text or "Invalid Feishu response") from exc
    if not isinstance(payload, dict):
        raise FeishuApiError("invalid_json", "Feishu response was not a JSON object")
    if response.status_code >= 400:
        raise FeishuApiError("http_error", payload.get("msg") or response.text or str(response.status_code))
    if payload.get("code") not in (0, None):
        raise FeishuApiError("feishu_error", str(payload.get("msg") or payload.get("code")))
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def _message_text(raw: dict[str, Any]) -> str:
    body = raw.get("body") if isinstance(raw.get("body"), dict) else {}
    content_raw = body.get("content") if isinstance(body, dict) else raw.get("content")
    if not isinstance(content_raw, str) or not content_raw.strip():
        return ""
    try:
        parsed = json.loads(content_raw)
    except json.JSONDecodeError:
        return content_raw[:500]
    if isinstance(parsed, dict):
        text = parsed.get("text")
        if isinstance(text, str):
            return text[:1000]
    return content_raw[:500]


def _summarize_message(raw: dict[str, Any]) -> dict[str, Any]:
    sender = raw.get("sender") if isinstance(raw.get("sender"), dict) else {}
    sender_id = sender.get("id") if isinstance(sender, dict) else None
    create_time = raw.get("create_time")
    created_at = None
    if isinstance(create_time, str) and create_time.isdigit():
        created_at = datetime.fromtimestamp(int(create_time) / 1000, tz=timezone.utc).isoformat()
    return {
        "message_id": raw.get("message_id"),
        "chat_id": raw.get("chat_id"),
        "msg_type": raw.get("msg_type"),
        "sender_id": sender_id,
        "created_at": created_at,
        "text": _message_text(raw),
    }


def list_chats(access_token: str, *, api_base: str, page_size: int = 20) -> list[dict[str, Any]]:
    data = _request(
        access_token,
        "GET",
        api_base,
        "/open-apis/im/v1/chats",
        params={"page_size": max(1, min(page_size, 50))},
    )
    items = data.get("items") or []
    if not isinstance(items, list):
        return []
    chats: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        chats.append(
            {
                "chat_id": item.get("chat_id"),
                "name": item.get("name"),
                "chat_type": item.get("chat_type"),
                "description": item.get("description"),
            }
        )
    return chats


def list_messages(
    access_token: str,
    *,
    api_base: str,
    chat_id: str,
    page_size: int = 20,
) -> list[dict[str, Any]]:
    trimmed = chat_id.strip()
    if not trimmed:
        raise FeishuApiError("invalid_chat_id", "chat_id is required")
    data = _request(
        access_token,
        "GET",
        api_base,
        "/open-apis/im/v1/messages",
        params={
            "container_id_type": "chat",
            "container_id": trimmed,
            "page_size": max(1, min(page_size, 50)),
        },
    )
    items = data.get("items") or []
    if not isinstance(items, list):
        return []
    return [_summarize_message(item) for item in items if isinstance(item, dict)]


def get_doc_raw_content(access_token: str, *, api_base: str, document_id: str) -> dict[str, Any]:
    trimmed = document_id.strip()
    if not trimmed:
        raise FeishuApiError("invalid_document_id", "document_id is required")
    data = _request(
        access_token,
        "GET",
        api_base,
        f"/open-apis/docx/v1/documents/{trimmed}/raw_content",
    )
    content = str(data.get("content") or "")
    if len(content) > 12000:
        content = content[:12000] + "\n… [truncated]"
    return {"document_id": trimmed, "content": content}


def list_calendar_events(
    access_token: str,
    *,
    api_base: str,
    days_ahead: int = 7,
    page_size: int = 20,
) -> dict[str, Any]:
    calendars_data = _request(
        access_token,
        "GET",
        api_base,
        "/open-apis/calendar/v4/calendars",
        params={"page_size": 50},
    )
    calendar_list = calendars_data.get("calendar_list") or []
    if not isinstance(calendar_list, list):
        calendar_list = []
    calendar_id = None
    calendar_name = None
    for item in calendar_list:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "primary":
            calendar_id = item.get("calendar_id")
            calendar_name = item.get("summary")
            break
    if not calendar_id and calendar_list:
        first = calendar_list[0]
        if isinstance(first, dict):
            calendar_id = first.get("calendar_id")
            calendar_name = first.get("summary")
    if not calendar_id:
        raise FeishuApiError("no_calendar", "No Feishu calendar found for this user")

    now = int(time.time())
    end = now + max(1, min(days_ahead, 30)) * 86400
    events_data = _request(
        access_token,
        "GET",
        api_base,
        f"/open-apis/calendar/v4/calendars/{calendar_id}/events",
        params={
            "start_time": str(now),
            "end_time": str(end),
            "page_size": max(1, min(page_size, 50)),
        },
    )
    items = events_data.get("items") or []
    events: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            start = item.get("start") if isinstance(item.get("start"), dict) else {}
            end_time = item.get("end") if isinstance(item.get("end"), dict) else {}
            events.append(
                {
                    "event_id": item.get("event_id"),
                    "summary": item.get("summary"),
                    "description": (str(item.get("description") or "")[:500] or None),
                    "start": start.get("date_time") or start.get("date"),
                    "end": end_time.get("date_time") or end_time.get("date"),
                    "status": item.get("status"),
                }
            )
    return {
        "calendar_id": calendar_id,
        "calendar_name": calendar_name,
        "count": len(events),
        "events": events,
    }
