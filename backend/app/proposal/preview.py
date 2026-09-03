"""Proposal payload fingerprint helpers."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def proposal_state_fingerprint(state: dict[str, Any]) -> str:
    """Stable hash for change detection and client cache invalidation."""
    payload = json.dumps(state, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
