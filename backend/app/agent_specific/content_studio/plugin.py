"""Content Studio runtime plugin."""

from __future__ import annotations

from app.platform.runtime.plugin import AgentPlugin

CONTENT_STUDIO_TOOL_NAMES = frozenset(
    {
        "sandbox_run_command",
        "sandbox_read_file",
        "sandbox_write_file",
        "publish_artifact",
    }
)


class ContentStudioPlugin(AgentPlugin):
    slug = "content-studio"
    tool_names = CONTENT_STUDIO_TOOL_NAMES
