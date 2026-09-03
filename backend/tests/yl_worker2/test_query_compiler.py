"""Unit tests for ontology query_compiler."""

import pytest

from app.yl_worker2.runtime.query_compiler import QueryCompileError, compile_where

ALLOWED = {"product_code", "site_code", "site_type", "product_name"}


def test_compile_eq_single():
    sql, args, _ = compile_where({"eq": {"product_code": "MOCK_YLP001"}}, ALLOWED)
    assert sql == "product_code = $1"
    assert args == ["MOCK_YLP001"]


def test_compile_eq_multi_and():
    sql, args, _ = compile_where(
        {"eq": {"product_code": "P1", "site_code": "S1"}},
        ALLOWED,
    )
    assert "product_code = $1" in sql
    assert "site_code = $2" in sql
    assert args == ["P1", "S1"]


def test_compile_contains():
    sql, args, _ = compile_where({"contains": {"product_name": "牛奶片"}}, ALLOWED)
    assert sql == "product_name ILIKE $1"
    assert args == ["%牛奶片%"]


def test_compile_and_nested():
    where = {
        "and": [
            {"eq": {"site_type": 0}},
            {"contains": {"product_name": "牛奶"}},
        ]
    }
    sql, args, _ = compile_where(where, ALLOWED)
    assert "AND" in sql
    assert args == [0, "%牛奶%"]


def test_compile_rejects_unknown_column():
    with pytest.raises(QueryCompileError, match="column_not_allowed"):
        compile_where({"eq": {"secret_col": 1}}, ALLOWED)


def test_compile_resolves_column_aliases():
    aliases = {"site_code": "from_site_code"}
    allowed = {"from_site_code", "product_code"}
    sql, args, _ = compile_where(
        {"eq": {"site_code": "MOCK_WH_S03"}},
        allowed,
        column_aliases=aliases,
    )
    assert sql == "from_site_code = $1"
    assert args == ["MOCK_WH_S03"]


def test_compile_rejects_bad_op():
    with pytest.raises(QueryCompileError, match="unsupported_where_op"):
        compile_where({"raw_sql": "1=1"}, ALLOWED)
