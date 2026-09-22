"""Unit tests for chat fork helpers."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from agent_framework import Content, Message

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
async def test_fork_chat_copies_messages_and_annotations(monkeypatch) -> None:
    user_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    source_id = uuid.uuid4()
    turn_id = uuid.uuid4()
    message_id = uuid.uuid4()

    source = SimpleNamespace(
        id=source_id,
        user_id=user_id,
        agent_id=agent_id,
        title="LRQ overview",
    )
    source_messages = [
        SimpleNamespace(
            id=message_id,
            sequence=1,
            turn_id=turn_id,
            body=Message(role="user", contents=[Content.from_text("hi")]).to_dict(),
        ),
    ]
    source_annotations: list[SimpleNamespace] = []

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

    class _MessageRepo:
        def __init__(self, db):
            self._db = db

        async def list_by_chat(self, chat_id):
            assert chat_id == source_id
            return source_messages

        async def insert_many(self, chat_id, rows, *, flush=True):
            assert len(rows) == 1
            assert rows[0]["body"]["role"] == "user"
            return []

    class _AnnotationRepo:
        def __init__(self, db):
            self._db = db

        async def list_by_chat(self, chat_id):
            assert chat_id == source_id
            return source_annotations

        async def insert_many(self, chat_id, rows, *, flush=True):
            return []

    monkeypatch.setattr("app.platform.chat.fork_service.ChatMessageRepository", _MessageRepo)
    monkeypatch.setattr("app.platform.chat.fork_service.ChatUiAnnotationRepository", _AnnotationRepo)
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
        title="Private",
    )

    class _Db:
        def add(self, obj):
            pass

        async def flush(self):
            pass

    with pytest.raises(PermissionError):
        await fork_chat(_Db(), source=source, user_id=uuid.uuid4())
