"""PG-backed MAF HistoryProvider — canonical transcript SSOT."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from typing import Any

from agent_framework import HistoryProvider, Message
from agent_framework._sessions import filter_new_messages
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.chat_messages import ChatMessageRepository
from app.platform.memory.history_constants import HISTORY_SOURCE_ID
from app.platform.memory.maf_mapping import REASONING_CONTENT_PROVIDERS
from app.platform.llm.reasoning_content_mixin import coalesce_reasoning_tool_messages
from app.platform.memory.memory_config import MemoryConfig
from app.platform.memory.message_validate import (
    assert_no_tool_calls_in_partial_assistant,
    message_from_body,
    sanitize_messages_for_llm_history,
    validate_message_body,
)
logger = logging.getLogger(__name__)


def create_postgres_history_provider(
    db: AsyncSession,
    *,
    chat_id: uuid.UUID,
    turn_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    memory_config: MemoryConfig | None = None,
    model_provider: str | None = None,
) -> "PostgresHistoryProvider":
    return PostgresHistoryProvider(
        db,
        chat_id=chat_id,
        turn_id=turn_id,
        run_id=run_id,
        memory_config=memory_config,
        model_provider=model_provider,
    )


class PostgresHistoryProvider(HistoryProvider):
    """Load/save MAF messages from chat_messages (append-only)."""

    DEFAULT_SOURCE_ID = HISTORY_SOURCE_ID

    def __init__(
        self,
        db: AsyncSession,
        *,
        chat_id: uuid.UUID,
        turn_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
        memory_config: MemoryConfig | None = None,
        model_provider: str | None = None,
        source_id: str | None = None,
        load_messages: bool = True,
        store_inputs: bool = False,
        store_outputs: bool = True,
    ) -> None:
        super().__init__(
            source_id or self.DEFAULT_SOURCE_ID,
            load_messages=load_messages,
            store_inputs=store_inputs,
            store_outputs=store_outputs,
        )
        self._db = db
        self._chat_id = chat_id
        self._turn_id = turn_id
        self._run_id = run_id
        self._memory_config = memory_config
        self._model_provider = model_provider
        self._messages = ChatMessageRepository(db)

    async def get_messages(
        self,
        session_id: str | None,
        *,
        state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> list[Message]:
        del session_id, state, kwargs
        tail: int | None = None
        if self._memory_config is not None and self._memory_config.history_load.max_messages > 0:
            tail = self._memory_config.history_load.max_messages
        rows = await self._messages.list_by_chat(self._chat_id, tail=tail)
        messages = [message_from_body(row.body) for row in rows]
        messages = sanitize_messages_for_llm_history(messages)
        if (self._model_provider or "") in REASONING_CONTENT_PROVIDERS:
            messages = coalesce_reasoning_tool_messages(messages)
        # Slim projection runs in PlatformCompactionProvider.before_run only.
        # Applying it here as well strips text_reasoning → plain text and drops
        # reasoning_content, breaking DeepSeek/Qwen on the next model call.
        return messages

    async def save_messages(
        self,
        session_id: str | None,
        messages: Sequence[Message],
        *,
        state: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        del session_id, state, kwargs
        if not messages:
            return

        existing_rows = await self._messages.list_by_chat(self._chat_id)
        existing = [message_from_body(row.body) for row in existing_rows]
        new_messages = filter_new_messages(existing, list(messages))
        if not new_messages:
            return

        turn_id = self._turn_id
        if turn_id is None:
            logger.warning("PostgresHistoryProvider.save_messages without turn_id; skipping persist")
            return

        batch: list[dict[str, Any]] = []
        for message in new_messages:
            body = validate_message_body(message.to_dict())
            assert_no_tool_calls_in_partial_assistant(body)
            batch.append(
                {
                    "turn_id": turn_id,
                    "run_id": self._run_id,
                    "body": body,
                }
            )
        await self._messages.insert_many(self._chat_id, batch, flush=True)
