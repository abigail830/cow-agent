"""Shared fixtures for yl-worker2 tests."""

from __future__ import annotations

import os

import pytest
import pytest_asyncio

from app.config import get_settings
from app.yl_worker2.obda.queries import fetch_inventory_snapshot

MOCK_PRODUCT = "MOCK_YLP001"
MOCK_SNAPSHOT_DATE = "2026-07-13"
MOCK_SITE_ZHENGZHOU = "MOCK_WH_S04"
MOCK_SITE_TIANJIN_SALES = "MOCK_WH_S02"
MOCK_SITE_HUHEHAOTE = "MOCK_WH_S07"
MOCK_BASE_TIANJIN = "MOCK_WH_B02"


def yl_db_configured() -> bool:
    return bool(get_settings().yl_database_url or os.getenv("YL_DATABASE_URL"))


requires_yl_db = pytest.mark.skipif(
    not yl_db_configured(),
    reason="YL_DATABASE_URL not configured — skip integration tests",
)


@pytest_asyncio.fixture
async def require_p1_snapshot():
    """Skip integration tests unless P1 mock snapshot is loaded in YL PG."""
    if not yl_db_configured():
        pytest.skip("YL_DATABASE_URL not configured")
    snap = await fetch_inventory_snapshot(
        MOCK_PRODUCT, MOCK_SITE_ZHENGZHOU, MOCK_SNAPSHOT_DATE
    )
    if snap is None:
        pytest.skip(
            "P1 snapshot missing — run yl_mock_ylp001_p1_script1_snapshot.sql on YL_DATABASE_URL"
        )
    return snap
