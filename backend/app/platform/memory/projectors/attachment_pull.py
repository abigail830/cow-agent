"""Memory projector for attachment pull tools (read / analyze / search)."""

from __future__ import annotations

import json
from typing import Any

from app.config import get_settings
from app.platform.attachments.tool_result_slim import (
    build_persisted_attachment_payload,
    extract_tool_payload,
    is_attachment_pull_tool,
)
from app.platform.memory.memory_config import MemorySlimConfig
from app.platform.memory.projectors.base import SlimCallResult, SlimResult
from app.platform.memory.projectors.utils import mark_slimmed, preview_text


class AttachmentPullMemoryProjector:
    name = "attachment_pull"
    DEFAULT_REQUEST_CHARS = 120

    def matches(self, tool_name: str, *, message_type: str) -> bool:
        return is_attachment_pull_tool(tool_name)

    def slim_call(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        metadata: dict[str, Any],
        config: MemorySlimConfig,
    ) -> SlimCallResult:
        chars = config.request_chars_for(tool_name, default=self.DEFAULT_REQUEST_CHARS)
        attachment_id = str(arguments.get("attachment_id") or arguments.get("query") or "")
        preview = preview_text(attachment_id, chars, label=f"{tool_name}: ")
        return SlimCallResult(
            arguments={"_memory_preview": preview},
            metadata=mark_slimmed(metadata, projector=self.name),
        )

    def slim_result(
        self,
        *,
        tool_name: str,
        content: str | None,
        metadata: dict[str, Any],
        config: MemorySlimConfig,
    ) -> SlimResult:
        max_chars = get_settings().attachment_tool_result_max_chars
        payload = extract_tool_payload(content, metadata)
        slimmed = build_persisted_attachment_payload(tool_name, payload, max_chars=max_chars)
        summary = str(slimmed.get("summary") or slimmed.get("message") or "")
        if not summary and tool_name == "search_attachments":
            summary = f"search_attachments count={slimmed.get('count', 0)}"
        if not summary:
            summary = preview_text(json.dumps(slimmed, ensure_ascii=False), max_chars)
        return SlimResult(
            content=summary,
            metadata={
                **mark_slimmed(metadata, projector=self.name),
                "result": slimmed,
                "attachment_persist_slimmed": True,
            },
        )
