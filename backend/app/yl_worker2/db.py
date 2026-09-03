"""YL PostgreSQL connection helpers for yl-worker2 tools."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

import asyncpg

from app.config import get_settings


def parse_adjust_date(value: str) -> date:
    return date.fromisoformat(value)


def require_yl_database_url() -> str:
    url = get_settings().yl_database_url
    if not url:
        raise RuntimeError("YL_DATABASE_URL is not configured")
    return url


async def yl_connect() -> asyncpg.Connection:
    return await asyncpg.connect(require_yl_database_url())


def row_to_dict(row: asyncpg.Record | None) -> dict[str, Any] | None:
    if row is None:
        return None
    out: dict[str, Any] = {}
    for key, value in dict(row).items():
        if isinstance(value, Decimal):
            out[key] = float(value)
        else:
            out[key] = value
    return out


def rows_to_dicts(rows: list[asyncpg.Record]) -> list[dict[str, Any]]:
    return [row_to_dict(row) or {} for row in rows]
