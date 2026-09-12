"""Platform-wide current date/time tool."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.platform.agent.platform_time import platform_time


def test_platform_time_returns_structured_datetime():
    result = platform_time()
    assert isinstance(result, dict)
    assert "utc_iso" in result
    assert "date" in result
    assert result["local_timezone"] == "Asia/Shanghai"
    assert len(result["date"]) == 10  # YYYY-MM-DD
    assert result["year"] >= 2024
    assert 1 <= result["month"] <= 12
    assert 1 <= result["day"] <= 31
    assert isinstance(result["weekday"], str)
    assert isinstance(result["unix_timestamp"], int)


def test_platform_time_matches_server_clock():
    result = platform_time()
    now_utc = datetime.now(timezone.utc)
    parsed = datetime.fromisoformat(result["utc_iso"])
    assert abs((parsed - now_utc).total_seconds()) < 2

    local = datetime.fromisoformat(result["local_iso"])
    assert local.utcoffset() == ZoneInfo("Asia/Shanghai").utcoffset(local.replace(tzinfo=None))
