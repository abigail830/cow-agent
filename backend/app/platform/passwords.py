"""Password hashing helpers (bcrypt, one-way)."""

import bcrypt


def hash_password(plain: str) -> str:
    if not plain:
        raise ValueError("Password must not be empty")
    digest = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt())
    return digest.decode("utf-8")


def verify_password(plain: str, password_hash: str | None) -> bool:
    if not plain or not password_hash:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False
