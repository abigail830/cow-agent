#!/usr/bin/env python3
"""Sync agent profiles from backend/agents/*/ into the database.

Run locally after editing profile.yaml, mcp_servers.yaml, or skills:

    cd backend
    source .venv/bin/activate
    python scripts/sync_agent_profiles.py

Use the same DATABASE_URL as production to publish profile changes to Vercel.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import func, select

from app.db.models import AgentModel
from app.db.session import get_async_session_factory, init_db_engine
from app.platform.platform_sync import sync_platform_config
from app.platform.profile_loader import discover_agent_profiles

logger = logging.getLogger(__name__)


async def _run(*, dry_run: bool) -> int:
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
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    return asyncio.run(_run(dry_run=args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
