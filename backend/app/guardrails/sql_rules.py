"""Read-only SQL validation for SQL MCP run_query tools (postgres, mysql, …)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_FORBIDDEN = re.compile(
    r"\b("
    r"INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|MERGE|"
    r"GRANT|REVOKE|COPY|CALL|EXECUTE|DO|SET|VACUUM|REINDEX|COMMENT|LOCK"
    r")\b",
    re.IGNORECASE,
)
_LIMIT = re.compile(r"\bLIMIT\s+(\d+)\b", re.IGNORECASE)
_READ_ONLY_START = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)


@dataclass(frozen=True)
class SqlValidationResult:
    ok: bool
    reason: str = ""
    normalized_sql: str = ""


def _strip_comments(sql: str) -> str:
    without_line = re.sub(r"--[^\n]*", "", sql)
    return re.sub(r"/\*.*?\*/", "", without_line, flags=re.DOTALL)


def _strip_string_literals(sql: str) -> str:
    """Remove quoted literals before keyword scans (avoid '%co-create%' matching CREATE)."""
    without_single = re.sub(r"'(?:[^']|'')*'", "''", sql)
    return re.sub(r'"(?:[^"]|"")*"', '""', without_single)


def _ensure_limit(sql: str, max_rows: int) -> str:
    match = _LIMIT.search(sql)
    if match:
        current = int(match.group(1))
        if current > max_rows:
            return _LIMIT.sub(f"LIMIT {max_rows}", sql, count=1)
        return sql
    return f"{sql.rstrip()} LIMIT {max_rows}"


def validate_sql(query: str, *, max_rows: int = 2000) -> SqlValidationResult:
    """Validate a read-only SQL query and optionally inject/normalize LIMIT."""
    if not query or not str(query).strip():
        return SqlValidationResult(ok=False, reason="Empty SQL query")

    if max_rows < 1:
        return SqlValidationResult(ok=False, reason="max_rows must be at least 1")

    cleaned = _strip_comments(str(query)).strip().rstrip(";")
    if not cleaned:
        return SqlValidationResult(ok=False, reason="Empty SQL query after removing comments")

    if ";" in cleaned:
        return SqlValidationResult(ok=False, reason="Multiple SQL statements are not allowed")

    if not _READ_ONLY_START.match(cleaned):
        return SqlValidationResult(ok=False, reason="Only SELECT queries (including WITH/CTE) are allowed")

    if _FORBIDDEN.search(_strip_string_literals(cleaned)):
        return SqlValidationResult(ok=False, reason="Only read-only SELECT queries are allowed")

    normalized = _ensure_limit(cleaned, max_rows)
    return SqlValidationResult(ok=True, normalized_sql=normalized)
