"""Verify yl-worker1 agent exposes postgres MCP tools on Agent.mcp_tools."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db.models import AgentModel
from app.platform.agent_factory import AgentFactory
from app.platform.profile_loader import discover_agent_profiles


async def main() -> int:
    settings = get_settings()
    engine = create_async_engine(settings.async_database_url, **{"connect_args": settings.async_database_connect_args})
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    profiles = discover_agent_profiles()
    profile = next((p for p in profiles if p.slug == "yl-worker1"), None)
    if profile is None:
        print("FAIL: yl-worker1 profile not found")
        return 1

    print(f"Profile allowed_tools: {profile.extra_config.get('allowed_tools')}")

    async with session_factory() as db:
        row = (await db.execute(select(AgentModel).where(AgentModel.slug == "yl-worker1"))).scalar_one_or_none()
        if row is None:
            print("FAIL: yl-worker1 agent row missing in DB — restart backend to sync")
            return 1

        bundle = await AgentFactory(db).build(row.id)
        print(f"Agent.mcp_tools count: {len(bundle.agent.mcp_tools)}")

        if not bundle.agent.mcp_tools:
            print("FAIL: no MCP tools on agent — postgres queries will not work")
            return 1

        async with bundle as agent:
            # run() path resolves MCP function names; peek connected tool names
            mcp = bundle.agent.mcp_tools[0]
            fn_names = sorted(f.name for f in mcp.functions)
            print(f"MCP server name: {mcp.name}")
            print(f"Exposed functions: {fn_names}")

        expected = {"list_tables", "describe_table", "get_schema", "query_data"}
        missing = expected - set(fn_names)
        if missing:
            print(f"FAIL: missing expected tools: {sorted(missing)}")
            return 1

        if "run_skill_script" in fn_names:
            print("WARN: run_skill_script should not be an MCP function")

    print("OK: postgres MCP tools are registered on agent")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
