#!/usr/bin/env python3
"""Sync agent profiles from backend/agents/*/ into the database.

Run locally after editing profile.yaml, mcp_servers.yaml, or skills:

    cd backend
    source .venv/bin/activate
    python scripts/sync_agent_profiles.py

Publish to Vercel production (use the DATABASE_URL from Vercel Dashboard, not a placeholder):

    python scripts/sync_agent_profiles.py --database-url "$VERCEL_DATABASE_URL" -v

Note: shell ``export DATABASE_URL=...`` is overwritten by backend/.env.local on import;
always pass ``--database-url`` when targeting a non-local database.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logger = logging.getLogger(__name__)


def _mask_database_target(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or "(unknown host)"
    db = (parsed.path or "").lstrip("/") or "(unknown db)"
    return f"{host}/{db}"


def _apply_database_url(url: str | None) -> None:
    if not url:
        return
    os.environ["DATABASE_URL"] = url
    from app.config import get_settings

    get_settings.cache_clear()
    import app.db.session as db_session

    db_session._engine = None
    db_session.async_session_factory = None


async def _run(*, dry_run: bool) -> int:
    from sqlalchemy import func, select

    from app.config import get_settings
    from app.db.models import AgentModel
    from app.db.session import get_async_session_factory, init_db_engine
    from app.platform.platform_sync import sync_platform_config
    from app.platform.profile_loader import discover_agent_profiles

    logger.info("Database target: %s", _mask_database_target(get_settings().database_url))
    init_db_engine()
    profiles = discover_agent_profiles()
    if not profiles:
        logger.error("No agent profiles found under backend/agents/")
        return 1

    logger.info("Discovered %d profile(s): %s", len(profiles), ", ".join(p.slug for p in profiles))
    if dry_run:
        logger.info("Dry run — no database changes written.")
        return 0

    factory = get_async_session_factory()
    async with factory() as session:
        await sync_platform_config(session)
        synced = (
            await session.execute(
                select(func.count()).select_from(AgentModel).where(AgentModel.slug.isnot(None))
            )
        ).scalar_one()
    logger.info("Sync complete: %d agent row(s) with slug in database.", synced)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List profiles on disk without writing to the database.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--database-url",
        metavar="URL",
        help="Override DATABASE_URL (required for Vercel prod; beats .env.local).",
    )
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    _apply_database_url(args.database_url)
    return asyncio.run(_run(dry_run=args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
