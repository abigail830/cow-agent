"""In-process pub/sub for attachment parse SSE (per chat_id)."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, AsyncIterator

_subscribers: dict[str, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)


async def subscribe_chat_parse_events(chat_id: str) -> AsyncIterator[dict[str, Any]]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    _subscribers[chat_id].append(queue)
    try:
        while True:
            yield await queue.get()
    finally:
        _subscribers[chat_id] = [q for q in _subscribers[chat_id] if q is not queue]
        if not _subscribers[chat_id]:
            _subscribers.pop(chat_id, None)


def publish_attachment_parse_updated(chat_id: str, payload: dict[str, Any]) -> None:
    event = {"type": "attachment.parse_updated", **payload}
    for queue in list(_subscribers.get(chat_id, [])):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass
