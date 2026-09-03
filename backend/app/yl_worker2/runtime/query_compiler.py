"""Compile structured filters to parameterized SQL WHERE clauses."""

from __future__ import annotations

import re
from typing import Any

_IDENT = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


class QueryCompileError(ValueError):
    pass


def _validate_column(
    name: str,
    allowed: set[str],
    *,
    column_aliases: dict[str, str] | None = None,
) -> str:
    col = (name or "").strip()
    if not col or not _IDENT.match(col):
        raise QueryCompileError(f"invalid_column:{name}")
    if col in allowed:
        return col
    if column_aliases:
        mapped = column_aliases.get(col)
        if mapped and mapped in allowed:
            return mapped
    raise QueryCompileError(f"column_not_allowed:{col}")


def compile_where(
    where: dict[str, Any] | None,
    allowed_columns: set[str],
    *,
    arg_offset: int = 1,
    column_aliases: dict[str, str] | None = None,
) -> tuple[str, list[Any], int]:
    if not where:
        return "TRUE", [], arg_offset

    op = next(iter(where))
    body = where[op]

    if op == "and":
        if not isinstance(body, list) or not body:
            raise QueryCompileError("and_requires_non_empty_list")
        parts: list[str] = []
        args: list[Any] = []
        idx = arg_offset
        for clause in body:
            frag, frag_args, idx = compile_where(
                clause,
                allowed_columns,
                arg_offset=idx,
                column_aliases=column_aliases,
            )
            parts.append(f"({frag})")
            args.extend(frag_args)
        return " AND ".join(parts), args, idx

    if op == "or":
        if not isinstance(body, list) or not body:
            raise QueryCompileError("or_requires_non_empty_list")
        parts = []
        args = []
        idx = arg_offset
        for clause in body:
            frag, frag_args, idx = compile_where(
                clause,
                allowed_columns,
                arg_offset=idx,
                column_aliases=column_aliases,
            )
            parts.append(f"({frag})")
            args.extend(frag_args)
        return " OR ".join(parts), args, idx

    if op == "eq" and isinstance(body, dict):
        clauses = []
        args: list[Any] = []
        idx = arg_offset
        for key, val in body.items():
            col = _validate_column(key, allowed_columns, column_aliases=column_aliases)
            clauses.append(f"{col} = ${idx}")
            args.append(val)
            idx += 1
        return " AND ".join(clauses), args, idx

    if op == "contains" and isinstance(body, dict):
        clauses = []
        args = []
        idx = arg_offset
        for key, val in body.items():
            col = _validate_column(key, allowed_columns, column_aliases=column_aliases)
            clauses.append(f"{col} ILIKE ${idx}")
            args.append(f"%{val}%")
            idx += 1
        return " AND ".join(clauses), args, idx

    if op == "gte" and isinstance(body, dict):
        clauses = []
        args = []
        idx = arg_offset
        for key, val in body.items():
            col = _validate_column(key, allowed_columns, column_aliases=column_aliases)
            clauses.append(f"{col} >= ${idx}")
            args.append(val)
            idx += 1
        return " AND ".join(clauses), args, idx

    if op == "lte" and isinstance(body, dict):
        clauses = []
        args = []
        idx = arg_offset
        for key, val in body.items():
            col = _validate_column(key, allowed_columns, column_aliases=column_aliases)
            clauses.append(f"{col} <= ${idx}")
            args.append(val)
            idx += 1
        return " AND ".join(clauses), args, idx

    if op == "is_null" and isinstance(body, dict):
        clauses = []
        args: list[Any] = []
        idx = arg_offset
        for key, val in body.items():
            col = _validate_column(key, allowed_columns, column_aliases=column_aliases)
            if val:
                clauses.append(f"{col} IS NULL")
            else:
                clauses.append(f"{col} IS NOT NULL")
        return " AND ".join(clauses), args, idx

    raise QueryCompileError(f"unsupported_where_op:{op}")
