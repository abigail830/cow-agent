"""Reuse E2B sandboxes within a single chat run (sync iterative edits)."""

from __future__ import annotations

import logging
import threading
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable

logger = logging.getLogger(__name__)

_session_key: ContextVar[str | None] = ContextVar("e2b_session_key", default=None)
_lock = threading.Lock()
_sessions: dict[str, "_HeldSandbox"] = {}


@dataclass
class _HeldSandbox:
    sandbox: Any
    workdir: str


def set_e2b_session_key(key: str | None) -> None:
    _session_key.set(key)


def get_e2b_session_key() -> str | None:
    return _session_key.get()


def acquire_e2b_sandbox(
    *,
    session_key: str,
    workdir: str,
    create_fn: Callable[[], Any],
) -> tuple[Any, bool]:
    """Return (sandbox, created_new). Reuses an existing sandbox for the session key."""
    with _lock:
        held = _sessions.get(session_key)
        if held is not None:
            return held.sandbox, False

    sandbox = create_fn()
    with _lock:
        held = _sessions.get(session_key)
        if held is not None:
            try:
                sandbox.kill()
            except Exception:
                logger.debug("E2B sandbox kill failed after race", exc_info=True)
            return held.sandbox, False
        _sessions[session_key] = _HeldSandbox(sandbox=sandbox, workdir=workdir)
        return sandbox, True


def get_e2b_workdir(session_key: str | None = None) -> str | None:
    key = session_key or get_e2b_session_key()
    if not key:
        return None
    with _lock:
        held = _sessions.get(key)
        return held.workdir if held else None


def release_e2b_session(session_key: str | None = None) -> None:
    key = session_key or get_e2b_session_key()
    if not key:
        return
    with _lock:
        held = _sessions.pop(key, None)
    if held is None:
        return
    try:
        held.sandbox.kill()
    except Exception:
        logger.debug("E2B sandbox kill failed on release", exc_info=True)
