"""Apply tool/skill slim projectors to platform message rows (used by MAF compaction)."""

from __future__ import annotations

from typing import Any

from app.memory.memory_config import MemoryConfig
from app.memory.projector_registry import MemoryProjectorRegistry, get_memory_projector_registry
from app.memory.projectors.skill import SkillMemoryProjector
from app.memory.projectors.utils import ensure_dict


class HistoryProjection:
    def __init__(
        self,
        registry: MemoryProjectorRegistry | None = None,
        *,
        skill_projector: SkillMemoryProjector | None = None,
    ) -> None:
        self._registry = registry or get_memory_projector_registry()
        self._skill = skill_projector or SkillMemoryProjector()

    def project_rows(self, rows: list[dict[str, Any]], memory_config: MemoryConfig) -> list[dict[str, Any]]:
        if not memory_config.slim.enabled:
            return [dict(row) for row in rows]

        call_args: dict[str, dict[str, Any]] = {}
        projected: list[dict[str, Any]] = []
        for row in rows:
            projected.append(self._project_row(dict(row), memory_config, call_args))
        return projected

    def _project_row(
        self,
        row: dict[str, Any],
        memory_config: MemoryConfig,
        call_args: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        message_type = row.get("message_type") or ""
        metadata = dict(row.get("metadata") or {})
        tool_name = str(metadata.get("tool_name") or "")

        if message_type.startswith("skill_") or tool_name in {"load_skill", "read_skill_resource"}:
            return self._skill.project_skill_row(row, memory_config.slim)

        if message_type in ("tool_call", "mcp_call"):
            arguments = ensure_dict(metadata.get("arguments"))
            call_id = str(metadata.get("call_id") or "")
            if call_id:
                call_args[call_id] = arguments
            projector = self._registry.resolve(tool_name, message_type=message_type)
            if not projector.matches(tool_name, message_type=message_type):
                return row
            slimmed = projector.slim_call(
                tool_name=tool_name,
                arguments=arguments,
                metadata=metadata,
                config=memory_config.slim,
            )
            return {
                **row,
                "metadata": {
                    **metadata,
                    **slimmed.metadata,
                    "arguments": slimmed.arguments,
                },
            }

        if message_type in ("tool_result", "mcp_result"):
            call_id = str(metadata.get("call_id") or "")
            paired_args = call_args.get(call_id, {})
            if paired_args and "arguments" not in metadata:
                metadata = {**metadata, "arguments": paired_args}
            projector = self._registry.resolve(tool_name, message_type=message_type)
            slimmed = projector.slim_result(
                tool_name=tool_name,
                content=row.get("content"),
                metadata=metadata,
                config=memory_config.slim,
            )
            return {
                **row,
                "content": slimmed.content,
                "metadata": {**metadata, **slimmed.metadata},
            }

        return row
