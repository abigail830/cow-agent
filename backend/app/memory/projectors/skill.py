"""Platform-unified Skill tool memory projector."""

from __future__ import annotations

from typing import Any

from app.memory.memory_config import MemorySlimConfig
from app.memory.projectors.base import SlimCallResult, SlimResult
from app.memory.projectors.utils import ensure_dict, mark_slimmed, preview_json

_SKILL_TOOLS = frozenset({"load_skill", "read_skill_resource"})


class SkillMemoryProjector:
    name = "skill"

    def matches(self, tool_name: str, *, message_type: str) -> bool:
        if tool_name in _SKILL_TOOLS:
            return True
        return message_type.startswith("skill_")

    def slim_call(
        self,
        *,
        tool_name: str,
        arguments: dict[str, Any],
        metadata: dict[str, Any],
        config: MemorySlimConfig,
    ) -> SlimCallResult:
        chars = config.request_chars_for(tool_name, default=120)
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
        args = ensure_dict(metadata.get("arguments"))
        if tool_name == "read_skill_resource":
            path = metadata.get("path") or metadata.get("resource_path") or args.get("path")
            summary = f"已读取 Skill 资源: {path}" if path else "已读取 Skill 资源"
        elif tool_name == "load_skill" or metadata.get("message_type") == "skill_load":
            skill = metadata.get("skill_name") or metadata.get("name") or args.get("skill_name")
            summary = f"已加载 Skill: {skill}" if skill else "已加载 Skill"
        else:
            skill = metadata.get("skill_name") or metadata.get("name")
            summary = f"已执行 Skill 操作: {skill}" if skill else "已执行 Skill 操作"
        return SlimResult(content=summary, metadata=mark_slimmed(metadata, projector=self.name))

    def project_skill_row(self, row: dict[str, Any], config: MemorySlimConfig) -> dict[str, Any]:
        metadata = row.get("metadata") or {}
        tool_name = metadata.get("tool_name") or row.get("message_type", "").replace("_", " ")
        slimmed = self.slim_result(
            tool_name=str(tool_name),
            content=row.get("content"),
            metadata=metadata,
            config=config,
        )
        return {
            **row,
            "content": slimmed.content,
            "metadata": slimmed.metadata,
        }
