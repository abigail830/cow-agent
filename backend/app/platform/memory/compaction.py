"""MAF CompactionProvider integration for platform slim + token-budget strategies."""

from __future__ import annotations

import logging
from typing import Any

from agent_framework import (
    CompactionProvider,
    ContextWindowCompactionStrategy,
    Message,
    SummarizationStrategy,
    ToolResultCompactionStrategy,
)

from app.platform.memory.maf_mapping import maf_messages_to_projection_rows, to_maf_messages
from app.platform.memory.memory_config import MemoryConfig
from app.platform.memory.redis_history import HISTORY_SOURCE_ID
from app.platform.memory.slimmer import HistoryProjection

logger = logging.getLogger(__name__)


class PlatformSlimCompactionStrategy:
    """Apply HistoryProjection slim rules to prior-turn MAF messages.

    Used only via PlatformCompactionProvider.before_run on the redis-history
    bucket. Do NOT attach as Agent.compaction_strategy: MAF apply_compaction runs
    on the full in-flight list (history + current turn), which would strip live
    skill/SQL payloads the model still needs within the same run.
    """

    def __init__(self, memory_config: MemoryConfig, *, projection: HistoryProjection | None = None) -> None:
        self._memory_config = memory_config
        self._projection = projection or HistoryProjection()

    async def __call__(self, messages: list[Message]) -> bool:
        if not self._memory_config.slim.enabled or not messages:
            return False

        rows = maf_messages_to_projection_rows(messages)
        projected = self._projection.project_rows(rows, self._memory_config)
        if _rows_unchanged(rows, projected):
            return False

        slimmed = to_maf_messages(projected)
        messages.clear()
        messages.extend(slimmed)
        return True


class PlatformCompactionProvider(CompactionProvider):
    """CompactionProvider that replaces history messages after slim (not just _excluded flags).

    MAF's default CompactionProvider.before_run filters by message object id after strategy
    mutation. Platform slim rebuilds Message instances, so we replace the history bucket
    in context_messages directly.
    """

    async def before_run(
        self,
        *,
        agent: Any,
        session: Any,
        context: Any,
        state: dict[str, Any],
    ) -> None:
        if self.before_strategy is None:
            return

        history_messages = context.context_messages.get(self.history_source_id)
        if not history_messages:
            return

        working = list(history_messages)
        if not working:
            return

        changed = await self.before_strategy(working)
        if changed:
            context.context_messages[self.history_source_id] = working


def build_in_run_compaction_strategy(memory_config: MemoryConfig) -> ContextWindowCompactionStrategy | None:
    """Token-budget compaction before each model call (Eve-style on-demand gate)."""
    compaction = memory_config.compaction
    if not compaction.enabled:
        return None
    return ContextWindowCompactionStrategy(
        max_context_window_tokens=compaction.max_context_window_tokens,
        max_output_tokens=compaction.max_output_tokens,
        tool_eviction_threshold=compaction.tool_eviction_threshold,
        truncation_threshold=compaction.truncation_threshold,
    )


def build_platform_compaction(
    memory_config: MemoryConfig,
    *,
    summarization_client: Any | None = None,
) -> tuple[ContextWindowCompactionStrategy | None, PlatformCompactionProvider | None]:
    """Return (in_run_strategy, compaction_provider).

    in_run_strategy is passed to Agent.compaction_strategy (per model call).
    compaction_provider handles before_run slim and after_run persistent compaction.
    """
    before_strategy: PlatformSlimCompactionStrategy | None = None
    if memory_config.slim.enabled:
        before_strategy = PlatformSlimCompactionStrategy(memory_config)

    after_strategy: SummarizationStrategy | ToolResultCompactionStrategy | None = None
    compaction = memory_config.compaction
    if compaction.enabled:
        if compaction.summarization.enabled and summarization_client is not None:
            after_strategy = SummarizationStrategy(
                client=summarization_client,
                target_count=compaction.summarization.target_count,
                threshold=compaction.summarization.threshold,
            )
        else:
            after_strategy = ToolResultCompactionStrategy(keep_last_tool_call_groups=2)

    provider: PlatformCompactionProvider | None = None
    if before_strategy is not None or after_strategy is not None:
        provider = PlatformCompactionProvider(
            before_strategy=before_strategy,
            after_strategy=after_strategy,
            history_source_id=HISTORY_SOURCE_ID,
        )

    in_run = build_in_run_compaction_strategy(memory_config)
    return in_run, provider


def _rows_unchanged(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> bool:
    if len(before) != len(after):
        return False
    for left, right in zip(before, after, strict=True):
        if left.get("content") != right.get("content"):
            return False
        if left.get("metadata") != right.get("metadata"):
            return False
    return True
