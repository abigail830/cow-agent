import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentTool, Tool
from app.tools import BUILTIN_TOOLS


class ToolRegistry:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_tools(self) -> list[Tool]:
        result = await self._db.execute(select(Tool).order_by(Tool.name))
        return list(result.scalars().all())

    async def resolve_for_agent(self, agent_id: uuid.UUID) -> list:
        result = await self._db.execute(
            select(Tool)
            .join(AgentTool, AgentTool.tool_id == Tool.id)
            .where(AgentTool.agent_id == agent_id)
            .order_by(Tool.name)
        )
        tools: list = []
        for row in result.scalars().all():
            resolved = self._resolve_tool(row)
            if resolved is not None:
                tools.append(resolved)
        return tools

    def _resolve_tool(self, row: Tool):
        definition = row.definition or {}
        if definition.get("kind") == "builtin":
            name = definition.get("name") or row.name
            return BUILTIN_TOOLS.get(name)
        return None
