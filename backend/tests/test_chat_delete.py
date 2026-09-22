"""Unit tests for chat delete cleanup."""

from __future__ import annotations

import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.platform.chat.delete_service import delete_chat, delete_chat_files
from app.platform.chat.run_manager import RunManager, RunStatus


@pytest.mark.asyncio
async def test_discard_chat_cancels_and_unregisters_run():
    manager = RunManager()
    chat_id = uuid.uuid4()
    run = await manager.start_run(chat_id, uuid.uuid4())
    finalized = False

    async def finalize() -> None:
        nonlocal finalized
        finalized = True

    await manager.register_finalize(run.run_id, finalize)
    discarded = await manager.discard_chat(chat_id)

    assert discarded is not None
    assert discarded.status == RunStatus.CANCELLED
    assert finalized is True
    assert await manager.get(run.run_id) is None
    assert await manager.cancel_for_chat(chat_id) is None


def test_delete_chat_files_removes_known_roots(tmp_path: Path, monkeypatch) -> None:
    chat_id = uuid.uuid4()
    roots = [
        tmp_path / "chat-artifacts",
        tmp_path / "proposal-artifacts",
        tmp_path / "chat-attachments",
    ]
    for root in roots:
        chat_dir = root / str(chat_id)
        chat_dir.mkdir(parents=True)
        (chat_dir / "keep-me.txt").write_text("x", encoding="utf-8")
        other = root / str(uuid.uuid4())
        other.mkdir()
        (other / "other.txt").write_text("y", encoding="utf-8")

    monkeypatch.setattr("app.platform.chat.delete_service._CHAT_FILE_ROOTS", tuple(roots))
    removed = delete_chat_files(chat_id)

    assert len(removed) == 3
    for root in roots:
        assert not (root / str(chat_id)).exists()
        leftover = next(root.iterdir())
        assert leftover.is_dir()


@pytest.mark.asyncio
async def test_delete_chat_commits_even_if_sidecars_fail(monkeypatch) -> None:
    chat_id = uuid.uuid4()
    chat = SimpleNamespace(id=chat_id)
    executed: list[object] = []
    committed = {"count": 0}

    class _Db:
        async def execute(self, stmt):
            executed.append(stmt)

        async def commit(self):
            committed["count"] += 1

    class _RunManager:
        async def discard_chat(self, cid):
            assert cid == chat_id
            raise RuntimeError("run registry down")

    class _SessionStore:
        def __init__(self, db):
            self._db = db

        async def delete_session(self, cid):
            assert cid == chat_id
            raise RuntimeError("redis down")

    monkeypatch.setattr("app.platform.chat.delete_service.get_run_manager", lambda: _RunManager())
    monkeypatch.setattr("app.platform.chat.delete_service.SessionStore", _SessionStore)
    monkeypatch.setattr("app.platform.chat.delete_service.delete_chat_files", lambda cid: (_ for _ in ()).throw(OSError("disk")))

    await delete_chat(_Db(), chat)

    assert len(executed) == 1
    assert committed["count"] == 1
