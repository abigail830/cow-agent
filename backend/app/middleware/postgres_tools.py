"""Backward-compatible re-exports for postgres SQL tool detection."""

from app.middleware.sql_tools import is_postgres_run_query

__all__ = ["is_postgres_run_query"]
