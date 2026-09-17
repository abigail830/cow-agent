"""Force hybrid-search tool calls to respect per-agent KB enable preferences."""

from __future__ import annotations

import json
import logging
from typing import Any

from agent_framework import FunctionInvocationContext, FunctionMiddleware

logger = logging.getLogger(__name__)

_HYBRID_SEARCH_NAMES = frozenset(
    {
        "hybrid_search",
        "hybrid-search_hybrid_search",
        "hybrid-search_list_knowledge_bases",
        "list_knowledge_bases",
    }
)


def _tool_names(context: FunctionInvocationContext) -> set[str]:
    names = {str(context.function.name or "")}
    props = context.function.additional_properties or {}
    for key in ("_mcp_normalized_name", "_mcp_remote_name"):
        value = props.get(key)
        if isinstance(value, str) and value.strip():
            names.add(value.strip())
    return names


def _is_hybrid_search(context: FunctionInvocationContext) -> bool:
    return bool(_tool_names(context) & {"hybrid_search", "hybrid-search_hybrid_search"})


def _is_list_knowledge_bases(context: FunctionInvocationContext) -> bool:
    return bool(_tool_names(context) & {"list_knowledge_bases", "hybrid-search_list_knowledge_bases"})


def _as_dict_arguments(arguments: Any) -> dict[str, Any]:
    if isinstance(arguments, dict):
        return dict(arguments)
    if hasattr(arguments, "model_dump"):
        dumped = arguments.model_dump()
        if isinstance(dumped, dict):
            return dumped
    return {}


def _normalize_kb_ids(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        return [text] if text else []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def resolve_scoped_kb_ids(*, requested: list[str] | None, enabled: list[str]) -> list[str]:
    """Intersect model-requested ids with enabled set; omit request → all enabled."""
    enabled_set = [kb_id for kb_id in enabled if kb_id]
    if not enabled_set:
        return []
    if not requested:
        return list(enabled_set)
    allowed = set(enabled_set)
    return [kb_id for kb_id in requested if kb_id in allowed]


def _parse_jsonish(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return value
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return value
    return value


def filter_list_knowledge_bases_result(result: Any, *, enabled_ids: list[str]) -> Any:
    """Drop disabled KBs from list_knowledge_bases payloads when possible."""
    enabled = set(enabled_ids)
    parsed = _parse_jsonish(result)
    if not isinstance(parsed, dict):
        return result

    items = parsed.get("items")
    visible = parsed.get("visible_ids")
    changed = False

    if isinstance(items, list):
        filtered_items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            kb_id = str(item.get("id") or "").strip()
            if kb_id and kb_id in enabled:
                filtered_items.append(item)
        if len(filtered_items) != len(items):
            parsed["items"] = filtered_items
            changed = True

    if isinstance(visible, list):
        filtered_visible = [str(item).strip() for item in visible if str(item).strip() in enabled]
        if filtered_visible != [str(item).strip() for item in visible if str(item).strip()]:
            parsed["visible_ids"] = filtered_visible
            changed = True

    if not changed:
        return result
    if isinstance(result, str):
        return json.dumps(parsed, ensure_ascii=False)
    return parsed


class KbScopeMiddleware(FunctionMiddleware):
    """Rewrite hybrid_search kb_ids and filter list_knowledge_bases results."""

    def __init__(self, *, enabled_kb_ids: list[str]) -> None:
        self._enabled = [str(item).strip() for item in enabled_kb_ids if str(item).strip()]

    async def process(self, context: FunctionInvocationContext, call_next) -> None:
        names = _tool_names(context)
        if not (names & _HYBRID_SEARCH_NAMES):
            await call_next()
            return

        if _is_hybrid_search(context):
            if not self._enabled:
                context.result = {
                    "error": "No knowledge bases are enabled for this agent.",
                    "hint": (
                        "Enable at least one knowledge base via the composer KB picker, "
                        "then retry hybrid_search."
                    ),
                }
                return

            args = _as_dict_arguments(context.arguments)
            requested = _normalize_kb_ids(args.get("kb_ids"))
            scoped = resolve_scoped_kb_ids(requested=requested or None, enabled=self._enabled)
            if not scoped:
                context.result = {
                    "error": "Requested knowledge bases are disabled for this agent.",
                    "hint": (
                        "Use only enabled knowledge bases from list_knowledge_bases "
                        f"(enabled={self._enabled})."
                    ),
                    "enabled_kb_ids": list(self._enabled),
                }
                return
            args["kb_ids"] = scoped
            context.arguments = args
            await call_next()
            return

        if _is_list_knowledge_bases(context):
            await call_next()
            if context.result is not None and self._enabled:
                context.result = filter_list_knowledge_bases_result(
                    context.result,
                    enabled_ids=self._enabled,
                )
            elif not self._enabled:
                # Keep shape similar to MCP list response.
                context.result = {
                    "visible_ids": [],
                    "items": [],
                    "error": "No knowledge bases are enabled for this agent.",
                }
            return

        await call_next()
