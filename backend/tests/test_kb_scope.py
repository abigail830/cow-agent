"""Unit tests for hybrid-search KB scope helpers and middleware rewrite."""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest

from app.platform.hooks.kb_scope import (
    KbScopeMiddleware,
    filter_list_knowledge_bases_result,
    resolve_scoped_kb_ids,
)
from app.platform.integrations.kb_client import resolve_hybrid_search_api_base
from app.platform.integrations.kb_preference import (
    agent_supports_kb_scope,
    enabled_kb_ids,
    invalidate_visible_kb_cache,
    resolve_enabled_kb_ids_for_run,
)


def test_agent_supports_kb_scope_from_allowed_tools() -> None:
    assert agent_supports_kb_scope({"allowed_tools": ["hybrid-search_hybrid_search"]})
    assert agent_supports_kb_scope({"mcp_servers": ["hybrid-search"]})
    assert not agent_supports_kb_scope({"allowed_tools": ["render_plantuml"]})


def test_enabled_kb_ids_defaults_all_on() -> None:
    assert enabled_kb_ids(visible_ids=["a", "b"], disabled_ids=[]) == ["a", "b"]
    assert enabled_kb_ids(visible_ids=["a", "b"], disabled_ids=["b"]) == ["a"]


@pytest.mark.asyncio
async def test_resolve_enabled_kb_ids_skips_remote_when_nothing_disabled(monkeypatch) -> None:
    invalidate_visible_kb_cache()

    class _Repo:
        async def get_disabled_ids(self, user_id, agent_id):
            return []

    monkeypatch.setattr(
        "app.platform.integrations.kb_preference.KbPreferenceRepository",
        lambda db: _Repo(),
    )

    called = {"list": False}

    async def _boom(*args, **kwargs):
        called["list"] = True
        raise AssertionError("should not list knowledge bases")

    monkeypatch.setattr(
        "app.platform.integrations.kb_preference.list_visible_knowledge_bases",
        _boom,
    )

    result = await resolve_enabled_kb_ids_for_run(
        object(),  # type: ignore[arg-type]
        user_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        api_key="okf_test",
    )
    assert result is None
    assert called["list"] is False


def test_resolve_scoped_kb_ids_intersects_request() -> None:
    assert resolve_scoped_kb_ids(requested=None, enabled=["a", "b"]) == ["a", "b"]
    assert resolve_scoped_kb_ids(requested=["b", "c"], enabled=["a", "b"]) == ["b"]
    assert resolve_scoped_kb_ids(requested=["c"], enabled=["a", "b"]) == []


def test_resolve_hybrid_search_api_base_from_mcp_url() -> None:
    settings = SimpleNamespace(
        hybrid_search_api_base=None,
        hybrid_search_mcp_url="https://cow-platform-ii.vercel.app/api/mcp/hybrid-search",
    )
    assert resolve_hybrid_search_api_base(settings) == "https://cow-platform-ii.vercel.app"


@pytest.mark.asyncio
async def test_kb_scope_middleware_rewrites_kb_ids() -> None:
    middleware = KbScopeMiddleware(enabled_kb_ids=["kb-1", "kb-2"])
    context = SimpleNamespace(
        function=SimpleNamespace(name="hybrid-search_hybrid_search", additional_properties={}),
        arguments={"query": "audit lifecycle", "kb_ids": ["kb-2", "kb-9"]},
        result=None,
    )

    async def call_next() -> None:
        return None

    await middleware.process(context, call_next)
    assert context.arguments["kb_ids"] == ["kb-2"]


@pytest.mark.asyncio
async def test_kb_scope_middleware_blocks_when_none_enabled() -> None:
    middleware = KbScopeMiddleware(enabled_kb_ids=[])
    context = SimpleNamespace(
        function=SimpleNamespace(name="hybrid_search", additional_properties={}),
        arguments={"query": "x"},
        result=None,
    )

    async def call_next() -> None:
        raise AssertionError("should not call next")

    await middleware.process(context, call_next)
    assert context.result["error"]


def test_filter_list_knowledge_bases_result() -> None:
    payload = {
        "visible_ids": ["a", "b", "c"],
        "items": [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}, {"id": "c", "name": "C"}],
    }
    filtered = filter_list_knowledge_bases_result(payload, enabled_ids=["b"])
    assert filtered["visible_ids"] == ["b"]
    assert [item["id"] for item in filtered["items"]] == ["b"]
