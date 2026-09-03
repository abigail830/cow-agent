import json

from app.db.readonly_sql import sql_tool_error_result


def test_sql_tool_error_result_includes_column_hint():
    payload = json.loads(
        sql_tool_error_result(
            Exception("column u.role does not exist"),
            query="SELECT u.role FROM users u",
        )
    )
    assert payload["ok"] is False
    assert payload["error_type"] == "Exception"
    assert "u.role" in payload["error"]
    assert "users has no role" in payload["hint"]
    assert "chat_messages.role" in payload["hint"]
    assert payload["query_preview"].startswith("SELECT u.role")


def test_sql_tool_error_result_includes_syntax_hint():
    payload = json.loads(sql_tool_error_result(Exception("syntax error at or near \"JSON_TABLE\"")))
    assert "PostgreSQL syntax error" in payload["hint"]
    assert "JSON_TABLE" in payload["hint"]


def test_sql_tool_error_result_validation_error():
    payload = json.loads(
        sql_tool_error_result(ValueError("Only read-only SQL queries are allowed"), query="DELETE FROM t")
    )
    assert payload["ok"] is False
    assert payload["error_type"] == "ValueError"
