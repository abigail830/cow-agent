import os

from app.platform import mcp_registry
from app.platform.mcp_registry import _build_native_db_tools


def test_vercel_uses_in_process_postgres_tools(monkeypatch):
    monkeypatch.setattr(mcp_registry, "IS_VERCEL", True)

    tools = _build_native_db_tools(
        "postgres",
        {"DATABASE_URL": "postgres://example"},
        ["list_tables", "query_data"],
    )

    assert tools is not None
    assert len(tools) == 2
    names = sorted(getattr(tool, "name", getattr(tool, "__name__", "")) for tool in tools)
    assert names == ["postgres_list_tables", "postgres_query_data"]


def test_vercel_uses_in_process_mysql_tools(monkeypatch):
    monkeypatch.setattr(mcp_registry, "IS_VERCEL", True)

    tools = _build_native_db_tools(
        "mysql",
        {
            "MYSQL_HOST": "db.example.com",
            "MYSQL_USER": "reader",
            "MYSQL_PASS": "secret",
            "MYSQL_DB": "analytics",
        },
        ["mysql_query"],
    )

    assert tools is not None
    assert len(tools) == 1
    assert getattr(tools[0], "name", "") == "mysql_query"


def test_mcp_registry_skips_stdio_subprocess_on_vercel(monkeypatch):
    monkeypatch.setattr(mcp_registry, "IS_VERCEL", True)

    class FakeRow:
        name = "postgres"
        transport = "stdio"
        description = "postgres"
        connection = {"command": "npx", "args": ["-y", "mcp-postgres@latest"], "env": {}}

    result = mcp_registry.McpRegistry(db=object())._build_tool(FakeRow(), profile_allowed=[])
    assert result is None


def test_mcp_registry_uses_in_process_postgres_locally(monkeypatch):
    monkeypatch.setattr(mcp_registry, "IS_VERCEL", False)

    class FakeRow:
        name = "sg-sp-analysis:postgres"
        transport = "stdio"
        description = "postgres"
        connection = {
            "schema_version": 2,
            "transport": "stdio",
            "config": {
                "command": "npx",
                "args": ["-y", "mcp-postgres@latest"],
                "env": {
                    "DATABASE_URL": "postgresql://reader:secret@db.example.com/app",
                    "DB_READ_ONLY": "true",
                },
            },
            "tool_name": "postgres",
        }

    result = mcp_registry.McpRegistry(db=object())._build_tool(
        FakeRow(),
        profile_allowed=["postgres_query_data", "postgres_list_tables"],
    )
    assert isinstance(result, list)
    names = {getattr(tool, "name", "") for tool in result}
    assert "postgres_query_data" in names
    assert "postgres_list_tables" in names
