"""Memory projector protocol for platform history slimming."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from app.memory.memory_config import MemorySlimConfig


@dataclass
class SlimCallResult:
    arguments: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SlimResult:
    content: str | None
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryProjector(Protocol):
    def matches(self, tool_name: str, *, message_type: str) -> bool: ...

    def slim_call(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        metadata: dict[str, Any],
        config: MemorySlimConfig,
    ) -> SlimCallResult: ...

    def slim_result(
        self,
        *,
        tool_name: str,
        content: str | None,
        metadata: dict[str, Any],
        config: MemorySlimConfig,
    ) -> SlimResult: ...
