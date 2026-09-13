"""E2B sandbox stale-handle invalidation and reconnect."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.shared.sandbox.e2b_session import (
    acquire_e2b_sandbox,
    invalidate_e2b_sandbox,
    is_e2b_stale_sandbox_error,
    release_e2b_session,
    set_e2b_session_key,
)
from app.shared.sandbox.providers.content_studio import ContentStudioSandbox


def test_is_e2b_stale_sandbox_error_matches_timeout_messages() -> None:
    assert is_e2b_stale_sandbox_error(
        RuntimeError("The sandbox was not found: This error is likely due to sandbox timeout.")
    )
    assert is_e2b_stale_sandbox_error(
        RuntimeError(
            "the connection to sandbox abc ended before the stream completed: sandbox timeout"
        )
    )
    assert not is_e2b_stale_sandbox_error(RuntimeError("permission denied"))


def test_invalidate_e2b_sandbox_removes_cached_handle() -> None:
    killed: list[str] = []

    class _FakeSandbox:
        def kill(self) -> None:
            killed.append("yes")

    key = "chat-test-invalidate"
    set_e2b_session_key(key)
    try:
        acquire_e2b_sandbox(
            session_key=key,
            workdir="/home/user/content-studio",
            create_fn=lambda: _FakeSandbox(),
        )
        assert invalidate_e2b_sandbox(key) is True
        assert killed == ["yes"]

        sandbox, created = acquire_e2b_sandbox(
            session_key=key,
            workdir="/home/user/content-studio",
            create_fn=lambda: _FakeSandbox(),
        )
        assert created is True
        assert isinstance(sandbox, _FakeSandbox)
    finally:
        release_e2b_session(key)
        set_e2b_session_key(None)


def test_call_with_reconnect_retries_after_stale_error(monkeypatch: pytest.MonkeyPatch) -> None:
    key = "chat-test-reconnect"
    set_e2b_session_key(key)
    calls = 0

    class _StaleError(Exception):
        pass

    class _FakeCommands:
        def run(self, cmd: str, *, cwd: str, timeout: float) -> object:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise _StaleError("The sandbox was not found: sandbox timeout")
            return SimpleNamespace(stdout="ok", stderr="", exit_code=0)

    class _FakeFiles:
        def read(self, path: str) -> str:
            return ""

        def write(self, path: str, content: str) -> None:
            pass

    class _FakeSandbox:
        def __init__(self) -> None:
            self.commands = _FakeCommands()
            self.files = _FakeFiles()

        def kill(self) -> None:
            pass

    def _create() -> _FakeSandbox:
        return _FakeSandbox()

    sandbox = ContentStudioSandbox(api_key="test-key", template=None, reuse_session=True)
    monkeypatch.setattr(sandbox, "_create_sandbox", _create)

    try:
        result = sandbox.run_command("echo hi")
        assert result["stdout"] == "ok"
        assert result["exit_code"] == 0
        assert calls == 2
    finally:
        release_e2b_session(key)
        set_e2b_session_key(None)


def test_call_with_reconnect_does_not_retry_non_stale_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    key = "chat-test-no-retry"
    set_e2b_session_key(key)
    calls = 0

    class _FakeCommands:
        def run(self, cmd: str, *, cwd: str, timeout: float) -> object:
            nonlocal calls
            calls += 1
            raise RuntimeError("syntax error in script")

    class _FakeSandbox:
        def __init__(self) -> None:
            self.commands = _FakeCommands()

        def kill(self) -> None:
            pass

    sandbox = ContentStudioSandbox(api_key="test-key", template=None, reuse_session=True)
    monkeypatch.setattr(sandbox, "_create_sandbox", lambda: _FakeSandbox())

    try:
        with pytest.raises(RuntimeError, match="syntax error"):
            sandbox.run_command("bad")
        assert calls == 1
    finally:
        release_e2b_session(key)
        set_e2b_session_key(None)
