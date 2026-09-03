"""MAF CompactionProvider integration for platform slim projectors."""

from __future__ import annotations

from typing import Any

from agent_framework import CompactionProvider, Message

from app.memory.maf_mapping import maf_messages_to_projection_rows, to_maf_messages
from app.memory.memory_config import MemoryConfig
from app.memory.slimmer import HistoryProjection

HISTORY_SOURCE_ID = "postgres-history"


class PlatformSlimCompactionStrategy:
    """Apply HistoryProjection slim rules to prior-turn MAF messages.

    Used only via PlatformCompactionProvider.before_run on the postgres-history
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


def build_platform_compaction(memory_config: MemoryConfig) -> tuple[PlatformSlimCompactionStrategy | None, PlatformCompactionProvider | None]:
    """Return (strategy, provider) when slim is enabled; otherwise (None, None)."""
    if not memory_config.slim.enabled:
        return None, None

    strategy = PlatformSlimCompactionStrategy(memory_config)
    provider = PlatformCompactionProvider(
        before_strategy=strategy,
        history_source_id=HISTORY_SOURCE_ID,
    )
    return strategy, provider


def _rows_unchanged(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> bool:
    if len(before) != len(after):
        return False
    for left, right in zip(before, after, strict=True):
        if left.get("content") != right.get("content"):
            return False
        if left.get("metadata") != right.get("metadata"):
            return False
    return True
