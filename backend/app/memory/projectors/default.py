"""Platform fallback memory projector."""

from __future__ import annotations

from typing import Any

from app.memory.memory_config import MemorySlimConfig
from app.memory.projectors.base import SlimCallResult, SlimResult
from app.memory.projectors.utils import mark_slimmed, preview_json, preview_text


class DefaultMemoryProjector:
    name = "default"

    def matches(self, tool_name: str, *, message_type: str) -> bool:
        return True

    def slim_call(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        metadata: dict[str, Any],
        config: MemorySlimConfig,
    ) -> SlimCallResult:
        chars = config.request_chars_for(tool_name)
        preview = preview_json(arguments, chars)
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
        chars = config.request_chars_for(tool_name)
        result = metadata.get("result")
        if isinstance(result, str):
            preview = preview_text(result, chars)
        elif result is not None:
            preview = preview_json(result, chars)
        else:
            preview = preview_text(content or "", chars)
        return SlimResult(
            content=preview or None,
            metadata=mark_slimmed(metadata, projector=self.name),
        )
