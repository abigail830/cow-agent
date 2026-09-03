import uuid
from pathlib import Path
from typing import Any, Sequence

from agent_framework import SkillsProvider
from agent_framework._skills import FunctionTool, Skill as AgentSkillType
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentSkill, Skill

# backend/ — skill source_path is relative to this root (e.g. agents/yl-worker1/skills/...)
SKILLS_ROOT = Path(__file__).resolve().parents[2]


class _AutoApproveSkillsProvider(SkillsProvider):
    """SkillsProvider variant that executes skill tools without requiring approval.

    agent_framework>=1.10 registers load_skill / read_skill_resource /
    run_skill_script with approval_mode="always_require".  The intended
    companion is ToolApprovalMiddleware, but that middleware's multi-loop
    design is incompatible with PostgresHistoryProvider (it clears
    context.messages and re-runs the agent, causing the previously
    accumulated tool_use to vanish from context so Anthropic 400s on the
    orphaned tool_result).  Bypassing the approval requirement at tool
    registration time is safe here because the platform already guards
    tool access via AllowedToolsMiddleware.
    """

    def _create_tools(self, skills: Sequence[AgentSkillType]) -> list[FunctionTool]:  # type: ignore[override]
        tools = super()._create_tools(skills)
        for tool in tools:
            tool.approval_mode = "never_require"
        return tools


class SkillRegistry:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_skills(self) -> list[Skill]:
        result = await self._db.execute(select(Skill).order_by(Skill.name))
        return list(result.scalars().all())

    async def resolve_provider_for_agent(self, agent_id: uuid.UUID) -> SkillsProvider | None:
        result = await self._db.execute(
            select(Skill)
            .join(AgentSkill, AgentSkill.skill_id == Skill.id)
            .where(AgentSkill.agent_id == agent_id)
            .order_by(Skill.name)
        )
        paths: list[str | Path] = []
        for row in result.scalars().all():
            path = self._resolve_skill_path(row)
            if path is not None:
                paths.append(path)
        if not paths:
            return None
        return _AutoApproveSkillsProvider.from_paths(paths)

    def _resolve_skill_path(self, row: Skill) -> Path | None:
        if row.source_type != "file" or not row.source_path:
            return None
        path = SKILLS_ROOT / row.source_path
        return path if path.exists() else None
