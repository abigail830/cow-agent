"""OIP allocation row ↔ mock_branch_replenishment_order linking via remark."""

from __future__ import annotations

import re

_MOCK_NO_RE = re.compile(r"\|MOCK_NO:([^|]+)\|")
_CANCELLED_MARK = "[已作废]"


def embed_mock_no(remark: str, mock_no: str) -> str:
    base = remark or ""
    if _MOCK_NO_RE.search(base):
        return base
    return f"{base}|MOCK_NO:{mock_no}|"


def extract_mock_no(remark: str | None) -> str | None:
    if not remark:
        return None
    match = _MOCK_NO_RE.search(remark)
    return match.group(1) if match else None


def mark_cancelled_remark(remark: str | None) -> str:
    base = remark or ""
    if _CANCELLED_MARK in base:
        return base
    return f"{base}{_CANCELLED_MARK}"


def is_cancelled_remark(remark: str | None) -> bool:
    return bool(remark and _CANCELLED_MARK in remark)
