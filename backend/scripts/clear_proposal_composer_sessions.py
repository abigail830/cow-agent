"""Clear proposal-composer proposal session extensions.

Usage:
    python scripts/clear_proposal_composer_sessions.py          # dry run
    python scripts/clear_proposal_composer_sessions.py --apply  # update DB
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import func, or_, select, update

from app.db.models import AgentModel, Chat
from app.db.session import get_async_session_factory


PROPOSAL_AGENT_SLUG = "proposal-composer"
SESSION_KEYS = ("proposal_state", "proposal_draft")


async def main(apply: bool) -> None:
    factory = get_async_session_factory()
    async with factory() as session:
        agent_id = await session.scalar(
            select(AgentModel.id).where(AgentModel.slug == PROPOSAL_AGENT_SLUG)
        )
        if agent_id is None:
            print(f"No agent found for slug={PROPOSAL_AGENT_SLUG!r}.")
            return

        base_filter = Chat.agent_id == agent_id
        count = await session.scalar(select(func.count()).select_from(Chat).where(base_filter))
        has_proposal_extension = or_(
            Chat.session_state.has_key("proposal_state"),  # noqa: W601
            Chat.session_state.has_key("proposal_draft"),  # noqa: W601
        )
        dirty_count = await session.scalar(
            select(func.count())
            .select_from(Chat)
            .where(
                base_filter,
                Chat.session_state.is_not(None),
                has_proposal_extension,
            )
        )

        print(f"proposal-composer chats: {count or 0}")
        print(f"chats with proposal session extensions: {dirty_count or 0}")
        if not apply or not dirty_count:
            print("Dry run only. Re-run with --apply to clear session extensions.")
            return

        stmt = (
            update(Chat)
            .where(
                base_filter,
                Chat.session_state.is_not(None),
                has_proposal_extension,
            )
            .values(
                session_state=Chat.session_state.op("-")("proposal_state").op("-")(
                    "proposal_draft"
                )
            )
        )
        result = await session.execute(stmt)
        await session.commit()
        print(f"cleared chats: {result.rowcount or 0}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write changes to the database")
    args = parser.parse_args()
    asyncio.run(main(apply=args.apply))
