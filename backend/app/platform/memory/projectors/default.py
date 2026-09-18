"""Platform fallback memory projector."""

from __future__ import annotations

from typing import Any

from app.platform.memory.memory_config import MemorySlimConfig
from app.platform.memory.projectors.base import SlimCallResult, SlimResult
from app.platform.memory.projectors.utils import mark_slimmed, preview_json, preview_text, truncate_long_strings


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
        return SlimCallResult(
            arguments=truncate_long_strings(arguments, chars),
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
