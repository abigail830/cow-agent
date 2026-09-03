"""Create or update a platform user password (bcrypt hash in DB).

Usage (from backend/):
    python scripts/set_user_password.py --email user@example.com --name "Display Name"
    python scripts/set_user_password.py --email user@example.com --password 'secret'
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys

from sqlalchemy import select

from app.db.models import User
from app.db.session import get_async_session_factory, init_db_engine
from app.platform.passwords import hash_password


async def _upsert_user(email: str, name: str | None, password: str) -> None:
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise SystemExit("Email is required")

    init_db_engine()
    factory = get_async_session_factory()
    async with factory() as session:
        result = await session.execute(select(User).where(User.email == normalized_email))
        user = result.scalar_one_or_none()
        password_hash = hash_password(password)
        if user is None:
            user = User(email=normalized_email, name=name, password_hash=password_hash, is_active=True)
            session.add(user)
            action = "created"
        else:
            user.password_hash = password_hash
            user.is_active = True
            if name:
                user.name = name
            action = "updated"
        await session.commit()
        print(f"User {action}: {normalized_email} ({user.id})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Set platform user password (bcrypt hash).")
    parser.add_argument("--email", required=True, help="User email (login id)")
    parser.add_argument("--name", default=None, help="Display name (optional)")
    parser.add_argument(
        "--password",
        default=None,
        help="Plain password (omit to prompt securely)",
    )
    args = parser.parse_args()

    password = args.password
    if not password:
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm password: ")
        if password != confirm:
            print("Passwords do not match.", file=sys.stderr)
            raise SystemExit(1)
    if not password:
        raise SystemExit("Password must not be empty")

    asyncio.run(_upsert_user(args.email, args.name, password))


if __name__ == "__main__":
    main()
