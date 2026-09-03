"""Delete all proposal-composer chat history (chats, messages, attachments).

Also optionally clears Redis session keys and on-disk proposal artifact files.

Usage (from backend/):
    python scripts/delete_proposal_composer_chats.py
    python scripts/delete_proposal_composer_chats.py --apply
    python scripts/delete_proposal_composer_chats.py --apply --redis --artifacts
"""

from __future__ import annotations

import argparse
import asyncio
import shutil
from pathlib import Path

from sqlalchemy import delete, func, select

from app.db.models import AgentModel, Chat, ChatAttachment, Message
from app.db.redis_client import check_redis_connection, get_redis
from app.db.session import get_async_session_factory, init_db_engine
from app.proposal.storage import ARTIFACTS_ROOT

PROPOSAL_AGENT_SLUG = "proposal-composer"


async def _counts(session, agent_id) -> dict[str, int]:
    chat_filter = Chat.agent_id == agent_id
    chats = await session.scalar(select(func.count()).select_from(Chat).where(chat_filter)) or 0
    messages = await session.scalar(
        select(func.count())
        .select_from(Message)
        .join(Chat, Message.chat_id == Chat.id)
        .where(chat_filter)
    ) or 0
    attachments = await session.scalar(
        select(func.count())
        .select_from(ChatAttachment)
        .join(Chat, ChatAttachment.chat_id == Chat.id)
        .where(chat_filter)
    ) or 0
    return {"chats": chats, "messages": messages, "attachments": attachments}


async def _list_chat_ids(session, agent_id) -> list:
    result = await session.scalars(select(Chat.id).where(Chat.agent_id == agent_id))
    return list(result.all())


async def _clear_redis_sessions(chat_ids: list) -> int:
    if not chat_ids:
        return 0
    if not await check_redis_connection():
        print("Redis unavailable — skipped session key cleanup.")
        return 0
    client = get_redis()
    removed = 0
    for chat_id in chat_ids:
        key = f"session:{chat_id}"
        if await client.delete(key):
            removed += 1
    return removed


def _clear_artifact_dirs(chat_ids: list) -> int:
    removed = 0
    for chat_id in chat_ids:
        chat_dir = ARTIFACTS_ROOT / str(chat_id)
        if chat_dir.is_dir():
            shutil.rmtree(chat_dir)
            removed += 1
    return removed


async def main(
    *,
    apply: bool,
    clear_redis: bool,
    clear_artifacts: bool,
) -> None:
    init_db_engine()
    factory = get_async_session_factory()
    async with factory() as session:
        agent_id = await session.scalar(
            select(AgentModel.id).where(AgentModel.slug == PROPOSAL_AGENT_SLUG)
        )
        if agent_id is None:
            print(f"No agent found for slug={PROPOSAL_AGENT_SLUG!r}.")
            return

        counts = await _counts(session, agent_id)
        chat_ids = await _list_chat_ids(session, agent_id)

        print(f"Agent: {PROPOSAL_AGENT_SLUG} ({agent_id})")
        print(f"Chats: {counts['chats']}")
        print(f"Messages: {counts['messages']}")
        print(f"Attachments: {counts['attachments']}")

        if counts["chats"]:
            rows = await session.execute(
                select(Chat.title, Chat.id)
                .where(Chat.agent_id == agent_id)
                .order_by(Chat.updated_at.desc())
                .limit(5)
            )
            print("Recent chats (up to 5):")
            for title, chat_id in rows.all():
                label = (title or "New Chat").strip() or "New Chat"
                print(f"  - {label} ({chat_id})")

        if not apply:
            print("\nDry run only. Re-run with --apply to delete.")
            if clear_redis or clear_artifacts:
                print("(Redis / artifact cleanup also requires --apply.)")
            return

        if not chat_ids:
            print("\nNothing to delete.")
            return

        await session.execute(delete(Chat).where(Chat.agent_id == agent_id))
        await session.commit()
        print(f"\nDeleted {len(chat_ids)} chat(s) from database (messages/attachments cascaded).")

        if clear_redis:
            n = await _clear_redis_sessions(chat_ids)
            print(f"Cleared {n} Redis session key(s).")

        if clear_artifacts:
            n = _clear_artifact_dirs(chat_ids)
            root = Path(ARTIFACTS_ROOT)
            print(f"Removed {n} proposal artifact folder(s) under {root}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Permanently delete chats and related DB rows.",
    )
    parser.add_argument(
        "--redis",
        action="store_true",
        help="With --apply, also delete Redis session:{chat_id} keys.",
    )
    parser.add_argument(
        "--artifacts",
        action="store_true",
        help="With --apply, also delete data/proposal-artifacts/{chat_id}/ folders.",
    )
    args = parser.parse_args()
    asyncio.run(
        main(
            apply=args.apply,
            clear_redis=args.redis,
            clear_artifacts=args.artifacts,
        )
    )
