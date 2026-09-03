from app.middleware.sql_tools import is_mysql_run_query, is_postgres_run_query, is_sql_run_query


def test_postgres_run_query_names():
    assert is_postgres_run_query("postgres_query_data")
    assert is_postgres_run_query("query_data")
    assert is_postgres_run_query("mcp__postgres__run_query")
    assert not is_postgres_run_query("mysql_execute_query")


def test_mysql_run_query_names():
    assert is_mysql_run_query("mysql_query")
    assert is_mysql_run_query("mysql_execute_query")
    assert is_mysql_run_query("execute_query")
    assert is_mysql_run_query("mcp__mysql__mysql_query")
    assert is_mysql_run_query("mcp__mysql__execute_query")
    assert not is_mysql_run_query("postgres_query_data")


def test_sql_run_query_union():
    assert is_sql_run_query("postgres_query_data")
    assert is_sql_run_query("mysql_query")
    assert not is_sql_run_query("mysql_list_tables")
