"""JSON Patch helpers for proposal-composer tests."""

from __future__ import annotations

from typing import Any


def jp(*operations: dict[str, Any]) -> list[dict[str, Any]]:
    """Build a JSON Patch operation list."""
    return list(operations)


def replace(path: str, value: Any) -> dict[str, Any]:
    return {"op": "replace", "path": path, "value": value}


def add(path: str, value: Any) -> dict[str, Any]:
    return {"op": "add", "path": path, "value": value}


def remove(path: str) -> dict[str, Any]:
    return {"op": "remove", "path": path}
