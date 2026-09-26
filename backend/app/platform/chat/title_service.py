"""Background chat title generation after the 2nd user turn completes."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.db.models import Chat, ChatMessage
from app.db.repositories.chat_messages import ChatMessageRepository
from app.db.session import get_async_session_factory
from app.platform.attachments.materialize import split_user_prompt_text
from app.platform.llm.utility_models import UtilityModelRegistry, UtilityPurpose
from app.platform.memory.message_validate import message_from_body
from app.platform.memory.projectors.utils import preview_text

logger = logging.getLogger(__name__)

TITLE_LLM_APPLIED_KEY = "title_llm_applied"
TITLE_FINALIZED_KEY = "title_finalized"  # legacy: was set on schedule before LLM success
TITLE_MAX_CHARS = 12
USER_SNIPPET_MAX = 400
ASSISTANT_SNIPPET_MAX = 1200

_inflight: set[uuid.UUID] = set()


def _session_state(chat: Chat) -> dict[str, Any]:
    state = chat.session_state
    return state if isinstance(state, dict) else {}


def is_title_llm_applied(chat: Chat) -> bool:
    return bool(_session_state(chat).get(TITLE_LLM_APPLIED_KEY))


def _legacy_title_generation_failed(chat: Chat) -> bool:
    state = _session_state(chat)
    return bool(state.get(TITLE_FINALIZED_KEY)) and not state.get(TITLE_LLM_APPLIED_KEY)


def mark_title_llm_applied(chat: Chat) -> None:
    state = dict(chat.session_state or {})
    state[TITLE_LLM_APPLIED_KEY] = True
    state.pop(TITLE_FINALIZED_KEY, None)
    chat.session_state = state
    flag_modified(chat, "session_state")


def normalize_title(raw: str) -> str | None:
    title = (raw or "").strip().strip("\"'")
    if not title or title.lower() == "new chat":
        return None
    if len(title) > TITLE_MAX_CHARS:
        title = title[: TITLE_MAX_CHARS - 1].rstrip() + "…"
    return title


def _text_from_body(body: dict[str, Any], *, role: str) -> str:
    message = message_from_body(body)
    parts: list[str] = []
    for content in message.contents or []:
        if getattr(content, "type", None) != "text":
            continue
        text = (getattr(content, "text", None) or "").strip()
        if not text:
            continue
        if role == "user":
            text = split_user_prompt_text(text)
        if text:
            parts.append(text)
    return " ".join(parts)


def _attachment_label(body: dict[str, Any]) -> str | None:
    props = body.get("additional_properties") or body.get("additionalProperties") or {}
    platform = props.get("platform") if isinstance(props, dict) else {}
    attachments = platform.get("attachments") if isinstance(platform, dict) else None
    if not isinstance(attachments, list) or not attachments:
        return None
    first = attachments[0]
    if isinstance(first, dict):
        filename = str(first.get("filename") or "").strip()
        if filename:
            return filename
    return None


def _user_line(message: ChatMessage) -> str | None:
    text = _text_from_body(message.body, role="user")
    if not text:
        filename = _attachment_label(message.body)
        if filename:
            text = f"[Attachment: {filename}]"
    if not text:
        return None
    return f"User: {preview_text(text, USER_SNIPPET_MAX)}"


def _assistant_line(messages: list[ChatMessage]) -> str | None:
    parts: list[str] = []
    for message in messages:
        if message.role != "assistant":
            continue
        text = _text_from_body(message.body, role="assistant")
        if text:
            parts.append(text)
    if not parts:
        return None
    combined = " ".join(parts)
    return f"Assistant: {preview_text(combined, ASSISTANT_SNIPPET_MAX)}"


def build_title_prompt(*, turn_ids: tuple[uuid.UUID, uuid.UUID], messages: list[ChatMessage]) -> str:
    by_turn: dict[uuid.UUID, list[ChatMessage]] = {turn_id: [] for turn_id in turn_ids}
    for message in messages:
        if message.turn_id in by_turn:
            by_turn[message.turn_id].append(message)

    lines: list[str] = []
    for turn_id in turn_ids:
        turn_messages = by_turn[turn_id]
        user_messages = [row for row in turn_messages if row.role == "user"]
        if user_messages:
            user_line = _user_line(user_messages[0])
            if user_line:
                lines.append(user_line)
        assistant_line = _assistant_line(turn_messages)
        if assistant_line:
            lines.append(assistant_line)
    return "\n".join(lines)


async def maybe_schedule_chat_title_generation(
    db: AsyncSession,
    *,
    chat_id: uuid.UUID,
    user_message_id: uuid.UUID,
) -> None:
    chat = await db.get(Chat, chat_id)
    if chat is None or is_title_llm_applied(chat):
        return

    user_messages = await ChatMessageRepository(db).list_user_messages_by_chat(chat_id)
    if len(user_messages) < 2:
        return

    second_user = user_messages[1]
    latest_user = user_messages[-1]
    is_second_turn = second_user.id == user_message_id
    is_failed_retry = _legacy_title_generation_failed(chat) and latest_user.id == user_message_id
    if not is_second_turn and not is_failed_retry:
        return

    turn_ids = (user_messages[0].turn_id, second_user.turn_id)
    schedule_chat_title_generation(chat_id, turn_ids=turn_ids)


def schedule_chat_title_generation(
    chat_id: uuid.UUID,
    *,
    turn_ids: tuple[uuid.UUID, uuid.UUID],
) -> None:
    if chat_id in _inflight:
        return
    _inflight.add(chat_id)
    asyncio.create_task(_generate_title_safe(chat_id, turn_ids=turn_ids))


async def _generate_title_safe(
    chat_id: uuid.UUID,
    *,
    turn_ids: tuple[uuid.UUID, uuid.UUID],
) -> None:
    try:
        await generate_chat_title(chat_id, turn_ids=turn_ids)
    except Exception:
        logger.exception("chat title generation failed chat_id=%s", chat_id)
    finally:
        _inflight.discard(chat_id)


async def generate_chat_title(
    chat_id: uuid.UUID,
    *,
    turn_ids: tuple[uuid.UUID, uuid.UUID],
) -> None:
    factory = get_async_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ChatMessage)
            .where(
                ChatMessage.chat_id == chat_id,
                ChatMessage.turn_id.in_(turn_ids),
            )
            .order_by(ChatMessage.sequence)
        )
        messages = list(result.scalars().all())
        prompt = build_title_prompt(turn_ids=turn_ids, messages=messages)
        if not prompt:
            return

        title = await UtilityModelRegistry().complete(
            UtilityPurpose.CHAT_TITLE,
            prompt=prompt,
            max_tokens=64,
            temperature=0.2,
        )
        normalized = normalize_title(title)
        if not normalized:
            return

        chat = await session.get(Chat, chat_id)
        if chat is None:
            return
        chat.title = normalized
        mark_title_llm_applied(chat)
        await session.commit()
        logger.info("chat title generated chat_id=%s title=%r", chat_id, normalized)
