from datetime import datetime, timezone

from agent_framework import tool


@tool(name="platform_time", description="Return the current UTC timestamp in ISO-8601 format.")
def platform_time() -> str:
    return datetime.now(timezone.utc).isoformat()
