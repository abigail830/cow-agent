"""Tests for background chat title generation."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agent_framework import Content, Message

from app.db.models import Chat, ChatMessage
from app.platform.chat.title_service import (
    build_title_prompt,
    generate_chat_title,
    is_title_llm_applied,
    mark_title_llm_applied,
    maybe_schedule_chat_title_generation,
    normalize_title,
    schedule_chat_title_generation,
    TITLE_FINALIZED_KEY,
)
from app.platform.llm.utility_models import UtilityModelRegistry, _uses_azure_responses_api


def test_normalize_title_rejects_placeholder() -> None:
    assert normalize_title("New Chat") is None
    assert normalize_title('"BVI 公司注册"') == "BVI 公司注册"


def test_build_title_prompt_uses_first_two_turns_only() -> None:
    turn1 = uuid.uuid4()
    turn2 = uuid.uuid4()
    turn3 = uuid.uuid4()
    user1 = ChatMessage(
        id=uuid.uuid4(),
        chat_id=uuid.uuid4(),
        sequence=1,
        turn_id=turn1,
        role="user",
        body=Message(role="user", contents=[Content.from_text("帮我写 BVI proposal")]).to_dict(),
    )
    assistant1 = ChatMessage(
        id=uuid.uuid4(),
        chat_id=user1.chat_id,
        sequence=2,
        turn_id=turn1,
        role="assistant",
        body=Message(role="assistant", contents=[Content.from_text("好的，我先确认 jurisdiction。")]).to_dict(),
    )
    user2 = ChatMessage(
        id=uuid.uuid4(),
        chat_id=user1.chat_id,
        sequence=3,
        turn_id=turn2,
        role="user",
        body=Message(role="user", contents=[Content.from_text("客户是 Demo Ltd")]).to_dict(),
    )
    assistant2 = ChatMessage(
        id=uuid.uuid4(),
        chat_id=user1.chat_id,
        sequence=4,
        turn_id=turn2,
        role="assistant",
        body=Message(role="assistant", contents=[Content.from_text("收到，我来整理服务范围。")]).to_dict(),
    )
    user3 = ChatMessage(
        id=uuid.uuid4(),
        chat_id=user1.chat_id,
        sequence=5,
        turn_id=turn3,
        role="user",
        body=Message(role="user", contents=[Content.from_text("第三轮不应出现")]).to_dict(),
    )

    prompt = build_title_prompt(
        turn_ids=(turn1, turn2),
        messages=[user1, assistant1, user2, assistant2, user3],
    )
    assert "帮我写 BVI proposal" in prompt
    assert "客户是 Demo Ltd" in prompt
    assert "收到，我来整理服务范围。" in prompt
    assert "第三轮不应出现" not in prompt


def test_title_llm_applied_flag_in_session_state() -> None:
    chat = Chat(user_id=uuid.uuid4(), agent_id=uuid.uuid4(), title="New Chat", session_state={})
    assert not is_title_llm_applied(chat)
    mark_title_llm_applied(chat)
    assert is_title_llm_applied(chat)
    assert chat.session_state == {"title_llm_applied": True}


def test_utility_client_routes_openai_compatible_providers() -> None:
    from agent_framework.openai import OpenAIChatCompletionClient

    registry = UtilityModelRegistry()
    client = registry.get_client()
    assert isinstance(client, OpenAIChatCompletionClient)
    assert _uses_azure_responses_api("https://api.siliconflow.cn/v1") is False
    assert _uses_azure_responses_api("https://smart-sales.cognitiveservices.azure.com/openai") is True


@pytest.mark.asyncio
async def test_maybe_schedule_only_on_second_user_turn() -> None:
    chat_id = uuid.uuid4()
    turn1 = uuid.uuid4()
    turn2 = uuid.uuid4()
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()
    chat = Chat(id=chat_id, user_id=uuid.uuid4(), agent_id=uuid.uuid4(), title="hello", session_state={})

    db = AsyncMock()
    db.get = AsyncMock(return_value=chat)
    db.commit = AsyncMock()

    repo = AsyncMock()
    repo.list_user_messages_by_chat = AsyncMock(
        return_value=[
            ChatMessage(
                id=user1_id,
                chat_id=chat_id,
                sequence=1,
                turn_id=turn1,
                role="user",
                body={},
            ),
            ChatMessage(
                id=user2_id,
                chat_id=chat_id,
                sequence=3,
                turn_id=turn2,
                role="user",
                body={},
            ),
        ]
    )

    with (
        patch("app.platform.chat.title_service.ChatMessageRepository", return_value=repo),
        patch("app.platform.chat.title_service.schedule_chat_title_generation") as schedule,
    ):
        await maybe_schedule_chat_title_generation(db, chat_id=chat_id, user_message_id=user1_id)
        schedule.assert_not_called()

        await maybe_schedule_chat_title_generation(db, chat_id=chat_id, user_message_id=user2_id)
        schedule.assert_called_once_with(chat_id, turn_ids=(turn1, turn2))
        assert not is_title_llm_applied(chat)


@pytest.mark.asyncio
async def test_maybe_schedule_retries_after_legacy_failed_generation() -> None:
    chat_id = uuid.uuid4()
    turn1 = uuid.uuid4()
    turn2 = uuid.uuid4()
    turn3 = uuid.uuid4()
    user1_id = uuid.uuid4()
    user2_id = uuid.uuid4()
    user3_id = uuid.uuid4()
    chat = Chat(
        id=chat_id,
        user_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        title="你好",
        session_state={TITLE_FINALIZED_KEY: True},
    )

    db = AsyncMock()
    db.get = AsyncMock(return_value=chat)
    repo = AsyncMock()
    repo.list_user_messages_by_chat = AsyncMock(
        return_value=[
            ChatMessage(id=user1_id, chat_id=chat_id, sequence=1, turn_id=turn1, role="user", body={}),
            ChatMessage(id=user2_id, chat_id=chat_id, sequence=3, turn_id=turn2, role="user", body={}),
            ChatMessage(id=user3_id, chat_id=chat_id, sequence=5, turn_id=turn3, role="user", body={}),
        ]
    )

    with (
        patch("app.platform.chat.title_service.ChatMessageRepository", return_value=repo),
        patch("app.platform.chat.title_service.schedule_chat_title_generation") as schedule,
    ):
        await maybe_schedule_chat_title_generation(db, chat_id=chat_id, user_message_id=user3_id)
        schedule.assert_called_once_with(chat_id, turn_ids=(turn1, turn2))


@pytest.mark.asyncio
async def test_generate_chat_title_persists_normalized_title() -> None:
    chat_id = uuid.uuid4()
    turn1 = uuid.uuid4()
    turn2 = uuid.uuid4()
    chat = Chat(id=chat_id, user_id=uuid.uuid4(), agent_id=uuid.uuid4(), title="hello", session_state={})
    messages = [
        ChatMessage(
            id=uuid.uuid4(),
            chat_id=chat_id,
            sequence=1,
            turn_id=turn1,
            role="user",
            body=Message(role="user", contents=[Content.from_text("帮我写 proposal")]).to_dict(),
        ),
        ChatMessage(
            id=uuid.uuid4(),
            chat_id=chat_id,
            sequence=2,
            turn_id=turn1,
            role="assistant",
            body=Message(role="assistant", contents=[Content.from_text("好的")]).to_dict(),
        ),
        ChatMessage(
            id=uuid.uuid4(),
            chat_id=chat_id,
            sequence=3,
            turn_id=turn2,
            role="user",
            body=Message(role="user", contents=[Content.from_text("客户 Demo Ltd")]).to_dict(),
        ),
        ChatMessage(
            id=uuid.uuid4(),
            chat_id=chat_id,
            sequence=4,
            turn_id=turn2,
            role="assistant",
            body=Message(role="assistant", contents=[Content.from_text("收到")]).to_dict(),
        ),
    ]

    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = messages
    session.execute = AsyncMock(return_value=result)
    session.get = AsyncMock(return_value=chat)
    session.commit = AsyncMock()

    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=session_cm)

    utility = AsyncMock()
    utility.complete = AsyncMock(return_value="BVI Proposal")

    with (
        patch("app.platform.chat.title_service.get_async_session_factory", return_value=factory),
        patch("app.platform.chat.title_service.UtilityModelRegistry", return_value=utility),
    ):
        await generate_chat_title(chat_id, turn_ids=(turn1, turn2))

    assert chat.title == "BVI Proposal"
    utility.complete.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_schedule_is_fire_and_forget() -> None:
    chat_id = uuid.uuid4()
    turn_ids = (uuid.uuid4(), uuid.uuid4())

    with patch("app.platform.chat.title_service.asyncio.create_task") as create_task:
        schedule_chat_title_generation(chat_id, turn_ids=turn_ids)
        create_task.assert_called_once()
