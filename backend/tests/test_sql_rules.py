from app.guardrails.sql_rules import validate_sql


def test_allows_select():
    result = validate_sql("SELECT 1", max_rows=100)
    assert result.ok
    assert "LIMIT 100" in result.normalized_sql


def test_denies_insert():
    result = validate_sql("INSERT INTO t VALUES (1)", max_rows=100)
    assert not result.ok


def test_denies_multiple_statements():
    result = validate_sql("SELECT 1; SELECT 2", max_rows=100)
    assert not result.ok


def test_caps_existing_limit():
    result = validate_sql("SELECT * FROM t LIMIT 5000", max_rows=2000)
    assert result.ok
    assert "LIMIT 2000" in result.normalized_sql


def test_allows_co_create_in_string_literal():
    result = validate_sql(
        "SELECT cs.id FROM chat_sessions cs WHERE cs.name ILIKE '%co-create%'",
        max_rows=100,
    )
    assert result.ok


def test_still_denies_create_table_outside_literals():
    result = validate_sql("CREATE TABLE t (id int)", max_rows=100)
    assert not result.ok
