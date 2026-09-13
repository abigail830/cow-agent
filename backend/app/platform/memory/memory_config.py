"""Parse agent profile memory settings."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


DEFAULT_WORKING_SET_TURNS = 20
DEFAULT_COLD_RESUME_MAX_TURNS = 10
DEFAULT_PREVIEW_CHARS = 200


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


DEFAULT_KEEP_FULL_ATTACHMENT_TURNS = 3
DEFAULT_DOC_SUMMARY_CHARS = 500


@dataclass(frozen=True)
class AttachmentCompactionConfig:
    enabled: bool = True
    keep_full_turns: int = DEFAULT_KEEP_FULL_ATTACHMENT_TURNS
    doc_summary_chars: int = DEFAULT_DOC_SUMMARY_CHARS


@dataclass(frozen=True)
class AttachmentPullConfig:
    enabled: bool = True
    first_turn_inline: bool = True
    search_enabled: bool = True


@dataclass(frozen=True)
class MemoryConfig:
    working_set_turns: int = DEFAULT_WORKING_SET_TURNS
    cold_resume_max_turns: int = DEFAULT_COLD_RESUME_MAX_TURNS
    slim: MemorySlimConfig = field(default_factory=MemorySlimConfig)
    long_term: LongTermMemoryConfig = field(default_factory=LongTermMemoryConfig)
    attachment_compaction: AttachmentCompactionConfig = field(default_factory=AttachmentCompactionConfig)
    attachment_pull: AttachmentPullConfig = field(default_factory=AttachmentPullConfig)

    def config_hash(self) -> str:
        payload = {
            "working_set_turns": self.working_set_turns,
            "cold_resume_max_turns": self.cold_resume_max_turns,
            "slim": {
                "enabled": self.slim.enabled,
                "default_preview_chars": self.slim.default_preview_chars,
                "tools": self.slim.tool_request_chars,
            },
            "long_term": {
                "enabled": self.long_term.enabled,
                "inject_max_tokens": self.long_term.inject_max_tokens,
            },
            "attachment_compaction": {
                "enabled": self.attachment_compaction.enabled,
                "keep_full_turns": self.attachment_compaction.keep_full_turns,
                "doc_summary_chars": self.attachment_compaction.doc_summary_chars,
            },
            "attachment_pull": {
                "enabled": self.attachment_pull.enabled,
                "first_turn_inline": self.attachment_pull.first_turn_inline,
                "search_enabled": self.attachment_pull.search_enabled,
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

    working_set_turns = int(memory.get("working_set_turns") or DEFAULT_WORKING_SET_TURNS)
    cold_resume_max_turns = int(memory.get("cold_resume_max_turns") or DEFAULT_COLD_RESUME_MAX_TURNS)
    long_term_raw = memory.get("long_term") or {}
    long_term = LongTermMemoryConfig(
        enabled=bool(long_term_raw.get("enabled", True)),
        inject_max_tokens=max(200, int(long_term_raw.get("inject_max_tokens") or 1500)),
    )

    compaction_raw = memory.get("attachment_compaction") or {}
    attachment_compaction = AttachmentCompactionConfig(
        enabled=bool(compaction_raw.get("enabled", True)),
        keep_full_turns=max(1, int(compaction_raw.get("keep_full_turns") or DEFAULT_KEEP_FULL_ATTACHMENT_TURNS)),
        doc_summary_chars=max(80, int(compaction_raw.get("doc_summary_chars") or DEFAULT_DOC_SUMMARY_CHARS)),
    )

    pull_raw = memory.get("attachment_pull") or {}
    attachment_pull = AttachmentPullConfig(
        enabled=bool(pull_raw.get("enabled", True)),
        first_turn_inline=bool(pull_raw.get("first_turn_inline", True)),
        search_enabled=bool(pull_raw.get("search_enabled", True)),
    )

    return MemoryConfig(
        working_set_turns=max(1, working_set_turns),
        cold_resume_max_turns=max(1, cold_resume_max_turns),
        slim=slim,
        long_term=long_term,
        attachment_compaction=attachment_compaction,
        attachment_pull=attachment_pull,
    )
