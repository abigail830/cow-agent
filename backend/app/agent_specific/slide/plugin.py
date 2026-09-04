"""Slide Studio runtime plugin."""

from __future__ import annotations

from app.agent_specific.slide.stream_emitter import SlideBuildStreamEmitter
from app.platform.runtime.plugin import AgentPlugin

SLIDE_TOOL_NAMES = frozenset({"render_slidev", "render_html_ppt"})


class SlidePlugin(AgentPlugin):
    slug = "slide-studio"
    tool_names = SLIDE_TOOL_NAMES

    def stream_emitters(self) -> list:
        return [SlideBuildStreamEmitter()]
