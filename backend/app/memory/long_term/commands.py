"""Parse explicit user memory commands (no auto-extraction)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.long_term.formatter import validate_line
from app.memory.long_term.repository import MemoryRepository, MemoryScope

_REMEMBER = re.compile(
    r"^(?:请记住|记住|please remember|remember)\s*(?:[：:,\s]\s*)?(.+)$",
    re.IGNORECASE,
)
_FORGET = re.compile(
    r"^(?:请忘掉|忘掉|不要再记住|删除记忆|forget)\s*(?:[：:,\s]\s*)?(.+)$",
    re.IGNORECASE,
)
_CONSTRAINT = re.compile(
    r"^(?:不要总是|别总是|禁止|请不要总是|never(?:\s+always)?|do not always)\s*(.+)$",
    re.IGNORECASE,
)

_USER_SCOPE_HINTS = ("以后都", "所有agent", "所有 agent", "全局", "always for all", "globally")
_AGENT_SCOPE_HINTS = ("这个agent", "这个 agent", "此agent", "此 agent", "在这个助手", "for this agent")


@dataclass(frozen=True)
class MemoryCommandResult:
    handled: bool
    is_pure_command: bool
    confirmation: str
    action: str
    scope: str
    lines: list[str]

    def to_dict(self) -> dict:
        return {
            "handled": self.handled,
            "is_pure_command": self.is_pure_command,
            "confirmation": self.confirmation,
            "action": self.action,
            "scope": self.scope,
            "lines": self.lines,
        }


@dataclass(frozen=True)
class _ParsedCommand:
    action: str  # append | remove | constraint
    payload: str
    is_pure: bool


def _detect_scope(payload: str, *, default_agent: bool) -> tuple[str, str]:
    """Return (scope, cleaned_payload)."""
    lower = payload.lower()
    if any(hint in lower for hint in _USER_SCOPE_HINTS):
        for hint in _USER_SCOPE_HINTS:
            payload = re.sub(re.escape(hint), "", payload, flags=re.IGNORECASE).strip(" ，,:：")
        return "user", payload
    if any(hint in lower for hint in _AGENT_SCOPE_HINTS):
        for hint in _AGENT_SCOPE_HINTS:
            payload = re.sub(re.escape(hint), "", payload, flags=re.IGNORECASE).strip(" ，,:：")
        return "agent", payload
    return ("agent" if default_agent else "user"), payload


def _parse_command(text: str) -> _ParsedCommand | None:
    raw = text.strip()
    if not raw:
        return None

    for pattern in (_REMEMBER,):
        match = pattern.match(raw)
        if match:
            payload = match.group(1).strip()
            if payload:
                return _ParsedCommand("append", payload, is_pure=True)

    for pattern in (_FORGET,):
        match = pattern.match(raw)
        if match:
            payload = match.group(1).strip()
            if payload:
                return _ParsedCommand("remove", payload, is_pure=True)

    match = _CONSTRAINT.match(raw)
    if match:
        payload = match.group(1).strip()
        if payload:
            return _ParsedCommand("constraint", payload, is_pure=True)

    return None


async def try_handle_memory_command(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    agent_id: uuid.UUID,
    content: str,
) -> MemoryCommandResult | None:
    """Handle explicit memory intents only. Returns None if message is not a memory command."""
    parsed = _parse_command(content)
    if parsed is None:
        return None

    repo = MemoryRepository(db)
    scope_name, payload = _detect_scope(parsed.payload, default_agent=parsed.action != "constraint")

    if parsed.action == "constraint":
        scope_name = "user"
        line = validate_line(f"[!] {payload}")
        memory_scope = MemoryScope("user")
        _, added = await repo.append_lines(user_id, memory_scope, [line], source="explicit")
        if not added:
            return MemoryCommandResult(
                handled=True,
                is_pure_command=parsed.is_pure,
                confirmation="该约束已在记忆中。",
                action="append",
                scope="user",
                lines=[],
            )
        return MemoryCommandResult(
            handled=True,
            is_pure_command=parsed.is_pure,
            confirmation=f"已记住约束：{payload}",
            action="append",
            scope="user",
            lines=added,
        )

    if parsed.action == "remove":
        memory_scope = MemoryScope("agent", agent_id=agent_id)
        removed_batches = await repo.remove_lines(
            user_id,
            memory_scope,
            match=payload,
            also_search_user_scope=True,
        )
        removed = [line for _, lines in removed_batches for line in lines]
        if not removed:
            return MemoryCommandResult(
                handled=True,
                is_pure_command=parsed.is_pure,
                confirmation=f"未找到与「{payload}」相关的记忆。",
                action="remove",
                scope="both",
                lines=[],
            )
        return MemoryCommandResult(
            handled=True,
            is_pure_command=parsed.is_pure,
            confirmation=f"已移除 {len(removed)} 条相关记忆。",
            action="remove",
            scope="both",
            lines=removed,
        )

    line = validate_line(f"- {payload}")
    memory_scope = MemoryScope(scope_name, agent_id=agent_id if scope_name == "agent" else None)
    _, added = await repo.append_lines(user_id, memory_scope, [line], source="explicit")
    scope_label = "全局偏好" if scope_name == "user" else "此 Agent 记忆"
    if not added:
        return MemoryCommandResult(
            handled=True,
            is_pure_command=parsed.is_pure,
            confirmation=f"该内容已在{scope_label}中。",
            action="append",
            scope=scope_name,
            lines=[],
        )
    return MemoryCommandResult(
        handled=True,
        is_pure_command=parsed.is_pure,
        confirmation=f"已记住（{scope_label}）：{payload}",
        action="append",
        scope=scope_name,
        lines=added,
    )
