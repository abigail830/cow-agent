"""Unit tests for chat fork helpers."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.platform.chat.fork_service import build_fork_title, fork_chat


def test_build_fork_title_prefixes_and_truncates() -> None:
    assert build_fork_title("Hello") == "fork-Hello"
    assert build_fork_title(None) == "fork-New Chat"
    assert build_fork_title("fork-Already") == "fork-Already"
    long_title = "x" * 80
    out = build_fork_title(long_title)
    assert out.startswith("fork-")
    assert len(out) <= 60
    assert out.endswith("…")


@pytest.mark.asyncio
async def test_fork_chat_copies_messages_and_rewrites_parents(monkeypatch) -> None:
    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    source_id = uuid.uuid4()
    parent_id = uuid.uuid4()
    child_id = uuid.uuid4()

    source = SimpleNamespace(
        id=source_id,
        user_id=user_id,
        agent_id=agent_id,
        title="LRQ overview",
    )
    source_messages = [
        SimpleNamespace(
            id=parent_id,
            role="user",
            content="hi",
            message_type="text",
            message_metadata={},
            parent_id=None,
            sequence=1,
        ),
        SimpleNamespace(
            id=child_id,
            role="assistant",
            content="hello",
            message_type="text",
            message_metadata={"streaming": False},
            parent_id=parent_id,
            sequence=2,
        ),
    ]

    added: list[object] = []
    flushed = {"count": 0}
    committed = {"count": 0}

    class _Db:
        def add(self, obj):
            added.append(obj)

        async def flush(self):
            flushed["count"] += 1
            for obj in added:
                if getattr(obj, "id", None) is None:
                    obj.id = uuid.uuid4()

        async def commit(self):
            committed["count"] += 1

        async def refresh(self, obj):
            return None

    class _Repo:
        def __init__(self, db):
            self._db = db

        async def list_by_chat(self, chat_id):
            assert chat_id == source_id
            return source_messages

        async def insert_many(self, chat_id, rows, *, flush=True):
            assert len(rows) == 2
            assert rows[0]["sequence"] == 1
            assert rows[1]["sequence"] == 2
            assert rows[1]["parent_id"] == rows[0]["message_id"]
            assert rows[0]["content"] == "hi"
            assert rows[1]["content"] == "hello"
            return []

    monkeypatch.setattr("app.platform.chat.fork_service.MessageRepository", _Repo)
    monkeypatch.setattr(
        "app.platform.chat.fork_service.Chat",
        lambda **kwargs: SimpleNamespace(id=None, **kwargs),
    )

    new_chat, src = await fork_chat(_Db(), source=source, user_id=user_id)
    assert src is source
    assert new_chat.title == "fork-LRQ overview"
    assert new_chat.agent_id == agent_id
    assert new_chat.user_id == user_id
    assert committed["count"] == 1
    assert flushed["count"] >= 1


@pytest.mark.asyncio
async def test_fork_chat_rejects_other_user() -> None:
    source = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        title="x",
    )
    with pytest.raises(PermissionError):
        await fork_chat(object(), source=source, user_id=uuid.uuid4())  # type: ignore[arg-type]
