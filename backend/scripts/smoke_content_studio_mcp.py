"""Verify content-studio MCP servers connect (hybrid-search + zhipu)."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import AgentModel
from app.platform.agent.agent_factory import AgentFactory


async def main() -> int:
    settings = get_settings()
    engine = create_async_engine(
        settings.async_database_url,
        connect_args=settings.async_database_connect_args,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as db:
        row = (
            await db.execute(select(AgentModel).where(AgentModel.slug == "content-studio"))
        ).scalar_one_or_none()
        if row is None:
            print("FAIL: content-studio agent row missing — run scripts/sync_agent_profiles.py")
            return 1

        bundle = await AgentFactory(db).build(row.id)
        print(f"Agent.mcp_tools count: {len(bundle.agent.mcp_tools)}")
        for tool in bundle.agent.mcp_tools:
            print(f"  - {tool.name} url={getattr(tool, 'url', None)}")

        if not bundle.agent.mcp_tools:
            print("FAIL: no MCP tools — check MCP_SECRETS_KEY and DB sync")
            return 1

        async with bundle as agent:
            for tool in bundle.agent.mcp_tools:
                fn_names = sorted(f.name for f in tool.functions)
                print(f"OK {tool.name}: {fn_names}")

    print("OK: content-studio MCP servers initialized")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
