"""Group message rows into user turns and apply turn-based windows."""

from __future__ import annotations

from typing import Any

_USER_TURN_TYPES = frozenset({"text", "run_cancelled"})


def is_turn_boundary(row: dict[str, Any]) -> bool:
    return row.get("role") == "user" and row.get("message_type") in _USER_TURN_TYPES


def group_messages_into_turns(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    turns: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []

    for row in rows:
        if is_turn_boundary(row) and current:
            turns.append(current)
            current = [row]
        else:
            current.append(row)

    if current:
        turns.append(current)
    return turns


def take_last_turns(rows: list[dict[str, Any]], max_turns: int) -> list[dict[str, Any]]:
    if max_turns <= 0 or not rows:
        return []
    turns = group_messages_into_turns(rows)
    selected = turns[-max_turns:] if len(turns) > max_turns else turns
    return [row for turn in selected for row in turn]
