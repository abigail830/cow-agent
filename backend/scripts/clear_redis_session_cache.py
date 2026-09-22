"""Clear Redis session hot-cache keys (session:{chat_id}).

Usage (from backend/):
    python scripts/clear_redis_session_cache.py
    python scripts/clear_redis_session_cache.py --dry-run
"""

from __future__ import annotations

import argparse
import asyncio

from app.db.redis_client import check_redis_connection, get_redis


async def clear_session_keys(*, dry_run: bool = False) -> int:
    if not await check_redis_connection():
        print("Redis unavailable — skipped session key cleanup.")
        return 0

    client = get_redis()
    keys: list[str] = []
    cursor = 0
    while True:
        cursor, batch = await client.scan(cursor, match="session:*", count=200)
        keys.extend(batch)
        if cursor == 0:
            break

    if not keys:
        print("No session:* keys found.")
        return 0

    if dry_run:
        print(f"Dry run — would delete {len(keys)} key(s):")
        for key in keys[:20]:
            print(f"  {key}")
        if len(keys) > 20:
            print(f"  ... and {len(keys) - 20} more")
        return 0

    removed = int(await client.delete(*keys))
    print(f"Deleted {removed} Redis session key(s).")
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description="Clear Redis session:{chat_id} hot cache.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List matching keys without deleting.",
    )
    args = parser.parse_args()
    asyncio.run(clear_session_keys(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
