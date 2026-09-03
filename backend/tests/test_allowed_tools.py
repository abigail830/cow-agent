from app.platform.allowed_tools import mcp_remote_tools_for_server, runtime_function_allowlist

PROFILE = [
    "postgres_list_tables",
    "postgres_describe_table",
    "postgres_get_schema",
    "postgres_query_data",
]


def test_mcp_remote_tools_for_postgres():
    assert mcp_remote_tools_for_server(PROFILE, "postgres") == [
        "list_tables",
        "describe_table",
        "get_schema",
        "query_data",
    ]


def test_mcp_remote_tools_legacy_run_query_alias():
    legacy = ["postgres_run_query", "postgres_list_tables"]
    assert mcp_remote_tools_for_server(legacy, "postgres") == [
        "query_data",
        "list_tables",
    ]


def test_mcp_remote_tools_none_when_unrestricted():
    assert mcp_remote_tools_for_server([], "postgres") is None


def test_runtime_allowlist():
    names = runtime_function_allowlist(PROFILE)
    assert names == {
        "postgres_list_tables",
        "list_tables",
        "postgres_describe_table",
        "describe_table",
        "postgres_get_schema",
        "get_schema",
        "postgres_query_data",
        "query_data",
    }


def test_mcp_double_underscore_remote_tools():
    legacy = [
        "mcp__postgres__list_tables",
        "mcp__postgres__describe_table",
        "mcp__postgres__run_query",
    ]
    assert mcp_remote_tools_for_server(legacy, "postgres") == [
        "list_tables",
        "describe_table",
        "query_data",
    ]


def test_runtime_allowlist_mcp_double_underscore():
    names = runtime_function_allowlist(
        ["mcp__postgres__run_query", "mcp__postgres__list_tables"]
    )
    assert "postgres_run_query" in names
    assert "query_data" in names
    assert "mcp__postgres__run_query" in names


MYSQL_PROFILE = ["mysql_query"]


def test_mcp_remote_tools_for_mysql():
    assert mcp_remote_tools_for_server(MYSQL_PROFILE, "mysql") == ["mysql_query"]


def test_runtime_allowlist_mysql_aliases():
    names = runtime_function_allowlist(MYSQL_PROFILE)
    assert "mysql_query" in names
    assert "mysql_mysql_query" in names
