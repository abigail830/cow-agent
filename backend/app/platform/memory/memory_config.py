"""Parse agent profile memory settings."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, replace
from typing import Any

from app.platform.llm.model_catalog import ModelEntry


DEFAULT_PREVIEW_CHARS = 200
DEFAULT_CONTEXT_WINDOW_TOKENS = 128_000
DEFAULT_MAX_OUTPUT_TOKENS = 16_384


@dataclass(frozen=True)
class MemorySlimConfig:
    enabled: bool = True
    default_preview_chars: int = DEFAULT_PREVIEW_CHARS
    tool_request_chars: dict[str, int] = field(default_factory=dict)

    def request_chars_for(self, tool_name: str, *, default: int | None = None) -> int:
        if tool_name in self.tool_request_chars:
            return self.tool_request_chars[tool_name]
        if default is not None:
            return default
        return self.default_preview_chars


@dataclass(frozen=True)
class LongTermMemoryConfig:
    enabled: bool = True
    inject_max_tokens: int = 1500


@dataclass(frozen=True)
class SummarizationCompactionConfig:
    enabled: bool = True
    target_count: int = 20
    threshold: int = 4


@dataclass(frozen=True)
class CompactionConfig:
    enabled: bool = True
    max_context_window_tokens: int = DEFAULT_CONTEXT_WINDOW_TOKENS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
    tool_eviction_threshold: float = 0.5
    truncation_threshold: float = 0.9
    summarization: SummarizationCompactionConfig = field(default_factory=SummarizationCompactionConfig)


@dataclass(frozen=True)
class HistoryLoadConfig:
    """Agent history load window (tail of transcript). 0 = unlimited."""

    max_messages: int = 200


@dataclass(frozen=True)
class MemoryConfig:
    slim: MemorySlimConfig = field(default_factory=MemorySlimConfig)
    long_term: LongTermMemoryConfig = field(default_factory=LongTermMemoryConfig)
    compaction: CompactionConfig = field(default_factory=CompactionConfig)
    history_load: HistoryLoadConfig = field(default_factory=HistoryLoadConfig)

    def config_hash(self) -> str:
        payload = {
            "slim": {
                "enabled": self.slim.enabled,
                "default_preview_chars": self.slim.default_preview_chars,
                "tools": self.slim.tool_request_chars,
            },
            "long_term": {
                "enabled": self.long_term.enabled,
                "inject_max_tokens": self.long_term.inject_max_tokens,
            },
            "compaction": {
                "enabled": self.compaction.enabled,
                "max_context_window_tokens": self.compaction.max_context_window_tokens,
                "max_output_tokens": self.compaction.max_output_tokens,
                "tool_eviction_threshold": self.compaction.tool_eviction_threshold,
                "truncation_threshold": self.compaction.truncation_threshold,
                "summarization": {
                    "enabled": self.compaction.summarization.enabled,
                    "target_count": self.compaction.summarization.target_count,
                    "threshold": self.compaction.summarization.threshold,
                },
            },
            "history_load": {
                "max_messages": self.history_load.max_messages,
            },
        }
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def parse_memory_config(agent_config: dict[str, Any] | None) -> MemoryConfig:
    cfg = agent_config or {}
    memory = cfg.get("memory") or {}
    slim_raw = memory.get("slim") or {}

    tool_chars: dict[str, int] = {}
    tools_raw = slim_raw.get("tools") or {}
    if isinstance(tools_raw, dict):
        for tool_name, tool_cfg in tools_raw.items():
            if not isinstance(tool_cfg, dict):
                continue
            chars = tool_cfg.get("request_chars")
            if isinstance(chars, int) and chars > 0:
                tool_chars[str(tool_name)] = chars

    slim = MemorySlimConfig(
        enabled=bool(slim_raw.get("enabled", True)),
        default_preview_chars=int(slim_raw.get("default_preview_chars") or DEFAULT_PREVIEW_CHARS),
        tool_request_chars=tool_chars,
    )

    long_term_raw = memory.get("long_term") or {}
    long_term = LongTermMemoryConfig(
        enabled=bool(long_term_raw.get("enabled", True)),
        inject_max_tokens=max(200, int(long_term_raw.get("inject_max_tokens") or 1500)),
    )

    compaction_raw = memory.get("compaction") or {}
    summarization_raw = compaction_raw.get("summarization") or {}
    summarization = SummarizationCompactionConfig(
        enabled=bool(summarization_raw.get("enabled", True)),
        target_count=max(1, int(summarization_raw.get("target_count") or 20)),
        threshold=max(0, int(summarization_raw.get("threshold") or 4)),
    )
    compaction = CompactionConfig(
        enabled=bool(compaction_raw.get("enabled", True)),
        max_context_window_tokens=max(
            1,
            int(compaction_raw.get("max_context_window_tokens") or DEFAULT_CONTEXT_WINDOW_TOKENS),
        ),
        max_output_tokens=max(0, int(compaction_raw.get("max_output_tokens") or DEFAULT_MAX_OUTPUT_TOKENS)),
        tool_eviction_threshold=float(compaction_raw.get("tool_eviction_threshold") or 0.5),
        truncation_threshold=float(compaction_raw.get("truncation_threshold") or 0.9),
        summarization=summarization,
    )

    history_load_raw = memory.get("history_load") or {}
    max_messages = int(history_load_raw.get("max_messages") or 200)
    history_load = HistoryLoadConfig(max_messages=max(0, max_messages))

    return MemoryConfig(slim=slim, long_term=long_term, compaction=compaction, history_load=history_load)


def apply_model_compaction_defaults(
    memory_config: MemoryConfig,
    model_entry: ModelEntry | None,
) -> MemoryConfig:
    """Overlay model-catalog context limits onto profile compaction settings."""
    if model_entry is None:
        return memory_config
    if model_entry.context_window_tokens is None and model_entry.max_output_tokens is None:
        return memory_config

    compaction = memory_config.compaction
    max_context_window_tokens = (
        model_entry.context_window_tokens
        if model_entry.context_window_tokens is not None
        else compaction.max_context_window_tokens
    )
    max_output_tokens = (
        model_entry.max_output_tokens
        if model_entry.max_output_tokens is not None
        else compaction.max_output_tokens
    )
    if max_output_tokens >= max_context_window_tokens:
        max_output_tokens = max(0, max_context_window_tokens // 8)

    return replace(
        memory_config,
        compaction=replace(
            compaction,
            max_context_window_tokens=max_context_window_tokens,
            max_output_tokens=max_output_tokens,
        ),
    )
