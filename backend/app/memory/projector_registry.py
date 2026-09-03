"""Resolve memory projectors: tool-family overrides with platform fallback."""

from __future__ import annotations

from collections.abc import Callable

from app.memory.projectors.base import MemoryProjector
from app.memory.projectors.default import DefaultMemoryProjector
from app.memory.projectors.skill import SkillMemoryProjector
from app.tools.memory_registry import register_tool_memory_projectors


class MemoryProjectorRegistry:
    def __init__(self) -> None:
        self._exact: dict[str, MemoryProjector] = {}
        self._predicates: list[tuple[Callable[[str], bool], MemoryProjector]] = []
        self._skill = SkillMemoryProjector()
        self._fallback = DefaultMemoryProjector()

    def register_exact(self, tool_name: str, projector: MemoryProjector) -> None:
        self._exact[tool_name] = projector

    def register_predicate(
        self,
        predicate: Callable[[str], bool],
        projector: MemoryProjector,
    ) -> None:
        self._predicates.append((predicate, projector))

    def resolve(self, tool_name: str, *, message_type: str) -> MemoryProjector:
        if self._skill.matches(tool_name, message_type=message_type):
            return self._skill
        if tool_name in self._exact:
            return self._exact[tool_name]
        for predicate, projector in self._predicates:
            if predicate(tool_name):
                return projector
        return self._fallback


_registry: MemoryProjectorRegistry | None = None


def get_memory_projector_registry() -> MemoryProjectorRegistry:
    global _registry
    if _registry is None:
        _registry = MemoryProjectorRegistry()
        register_tool_memory_projectors(_registry)
    return _registry
