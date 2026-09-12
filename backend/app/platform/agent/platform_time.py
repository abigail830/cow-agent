"""Platform-wide current date/time builtin tool."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from agent_framework import tool

PLATFORM_TIME_TOOL_NAME = "platform_time"
PLATFORM_ALWAYS_BUILTIN_TOOL_NAMES = frozenset({PLATFORM_TIME_TOOL_NAME})

_DEFAULT_LOCAL_TZ = ZoneInfo("Asia/Shanghai")


@tool(
    name=PLATFORM_TIME_TOOL_NAME,
    description=(
        "Return the server's real current date and time (not the model's training cutoff). "
        "Call this before web search, news, deadlines, scheduling, or any task that needs "
        "today's date, year, or recency filters. "
        "Returns UTC ISO timestamp, local time (Asia/Shanghai), and date parts "
        "(year, month, day, weekday)."
    ),
)
def platform_time() -> dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(_DEFAULT_LOCAL_TZ)
    return {
        "utc_iso": now_utc.isoformat(),
        "local_iso": now_local.isoformat(),
        "local_timezone": str(_DEFAULT_LOCAL_TZ),
        "date": now_local.strftime("%Y-%m-%d"),
        "year": now_local.year,
        "month": now_local.month,
        "day": now_local.day,
        "weekday": now_local.strftime("%A"),
        "unix_timestamp": int(now_utc.timestamp()),
    }
