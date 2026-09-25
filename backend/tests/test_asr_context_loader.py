from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.db.models import AgentModel, Chat
from app.platform.audio_capture.asr_context import load_asr_context_for_chat


@pytest.mark.asyncio
async def test_load_asr_context_uses_to_thread_for_profile(monkeypatch, tmp_path) -> None:
    chat_id = uuid.uuid4()
    agent_id = uuid.uuid4()
    to_thread_calls: list[object] = []

    async def fake_to_thread(func, /, *args, **kwargs):
        to_thread_calls.append(func)
        return SimpleNamespace(extra_config={"asr_context": "hotword"})

    class _Session:
        async def get(self, model, key):
            if model is Chat:
                return SimpleNamespace(id=chat_id, agent_id=agent_id)
            if model is AgentModel:
                return SimpleNamespace(slug="demo-agent")
            return None

    agent_dir = tmp_path / "demo-agent"
    agent_dir.mkdir()

    monkeypatch.setattr("app.platform.audio_capture.asr_context.asyncio.to_thread", fake_to_thread)
    monkeypatch.setattr("app.platform.audio_capture.asr_context.AGENTS_ROOT", tmp_path)

    result = await load_asr_context_for_chat(_Session(), chat_id)  # type: ignore[arg-type]

    assert result == "hotword"
    assert len(to_thread_calls) == 1
