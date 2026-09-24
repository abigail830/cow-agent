"""Context-window usage estimates aligned with slim + in-run compaction."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from agent_framework import CharacterEstimatorTokenizer, Message, annotate_message_groups, included_token_count
from agent_framework._compaction import annotate_token_counts
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.memory.compaction import PlatformSlimCompactionStrategy, build_in_run_compaction_strategy
from app.platform.memory.memory_config import MemoryConfig
from app.platform.memory.postgres_history import create_postgres_history_provider


@dataclass(frozen=True)
class ContextUsageSnapshot:
    tokens: int
    budget_tokens: int
    percent: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "tokens": self.tokens,
            "budget_tokens": self.budget_tokens,
            "percent": round(self.percent, 1),
        }


def input_budget_tokens(memory_config: MemoryConfig) -> int:
    compaction = memory_config.compaction
    return max(1, compaction.max_context_window_tokens - compaction.max_output_tokens)


def estimate_messages_token_count(messages: list[Any]) -> int:
    if not messages:
        return 0
    tokenizer = CharacterEstimatorTokenizer()
    annotate_message_groups(messages)
    annotate_token_counts(messages, tokenizer=tokenizer)
    return included_token_count(messages)


async def prepare_messages_for_usage_estimate(
    messages: list[Message],
    memory_config: MemoryConfig,
    *,
    chat_id: uuid.UUID | None = None,
    model_id: str | None = None,
    model_provider: str | None = None,
) -> list[Message]:
    """Apply the same slim + token-budget compaction used before each model call."""
    working = list(messages)
    if memory_config.slim.enabled:
        slim = PlatformSlimCompactionStrategy(
            memory_config,
            chat_id=chat_id,
            model_id=model_id,
            model_provider=model_provider,
        )
        await slim(working)
    in_run = build_in_run_compaction_strategy(memory_config)
    if in_run is not None:
        await in_run(working)
    return working


async def estimate_context_usage(
    *,
    db: AsyncSession,
    chat_id: uuid.UUID,
    memory_config: MemoryConfig,
    turn_id: uuid.UUID | None = None,
    run_id: uuid.UUID | None = None,
    model_id: str | None = None,
    model_provider: str | None = None,
) -> ContextUsageSnapshot | None:
    """Estimate post-compaction history tokens against the model input budget."""
    if not memory_config.compaction.enabled:
        return None

    budget = input_budget_tokens(memory_config)
    history = create_postgres_history_provider(
        db,
        chat_id=chat_id,
        turn_id=turn_id,
        run_id=run_id,
        memory_config=memory_config,
        model_id=model_id,
        model_provider=model_provider,
    )
    messages = await history.get_messages(str(chat_id))
    effective = await prepare_messages_for_usage_estimate(
        messages,
        memory_config,
        chat_id=chat_id,
        model_id=model_id,
        model_provider=model_provider,
    )
    tokens = estimate_messages_token_count(effective)
    percent = min(100.0, (tokens / budget) * 100.0) if budget > 0 else 0.0
    return ContextUsageSnapshot(tokens=tokens, budget_tokens=budget, percent=percent)
