"""Content hashing for attachment deduplication and registry keys."""

from __future__ import annotations

import hashlib


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def format_content_hash(hex_digest: str) -> str:
    return f"sha256:{hex_digest}"
