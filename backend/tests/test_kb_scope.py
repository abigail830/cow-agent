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
    KB_SCOPE_MEMORY_MARKER,
    agent_supports_kb_scope,
    enabled_kb_ids,
    format_kb_scope_memory_line,
    invalidate_visible_kb_cache,
    resolve_enabled_kb_ids_for_run,
    sync_enabled_kbs_to_agent_memory,
    upsert_kb_scope_memory_content,
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


def test_format_kb_scope_memory_line_with_enabled() -> None:
    line = format_kb_scope_memory_line(
        enabled_items=[{"id": "kb-1", "name": "LRQ"}, {"id": "kb-2", "name": "Corp"}]
    )
    assert line.startswith("[!]")
    assert KB_SCOPE_MEMORY_MARKER in line
    assert "LRQ (kb-1)" in line
    assert "Corp (kb-2)" in line


def test_format_kb_scope_memory_line_none_enabled() -> None:
    line = format_kb_scope_memory_line(enabled_items=[])
    assert "none enabled" in line
    assert "do not call hybrid_search" in line


def test_upsert_kb_scope_memory_content_preserves_other_bullets() -> None:
    existing = "- Prefer concise answers\n[!] Always cite sources"
    managed = format_kb_scope_memory_line(enabled_items=[{"id": "kb-1", "name": "LRQ"}])
    updated = upsert_kb_scope_memory_content(existing, line=managed)
    assert "- Prefer concise answers" in updated
    assert "[!] Always cite sources" in updated
    assert KB_SCOPE_MEMORY_MARKER in updated
    assert "LRQ (kb-1)" in updated

    replaced = upsert_kb_scope_memory_content(
        updated,
        line=format_kb_scope_memory_line(enabled_items=[{"id": "kb-9", "name": "Only"}]),
    )
    assert replaced.count(KB_SCOPE_MEMORY_MARKER) == 1
    assert "LRQ (kb-1)" not in replaced
    assert "Only (kb-9)" in replaced
    assert "- Prefer concise answers" in replaced

    cleared = upsert_kb_scope_memory_content(replaced, line=None)
    assert KB_SCOPE_MEMORY_MARKER not in cleared
    assert "- Prefer concise answers" in cleared
    assert "[!] Always cite sources" in cleared


@pytest.mark.asyncio
async def test_sync_enabled_kbs_clears_when_nothing_disabled(monkeypatch) -> None:
    calls: list[tuple] = []

    class _Repo:
        async def remove_lines(self, user_id, memory_scope, *, match, also_search_user_scope=False, agent_id_for_user=None):
            calls.append(("remove", match))
            return []

        async def append_lines(self, *args, **kwargs):
            raise AssertionError("should not append when all KBs enabled")

    monkeypatch.setattr(
        "app.platform.integrations.kb_preference.MemoryRepository",
        lambda db: _Repo(),
    )

    await sync_enabled_kbs_to_agent_memory(
        object(),  # type: ignore[arg-type]
        user_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        disabled_kb_ids=[],
        api_key="okf_test",
    )
    assert calls == [("remove", KB_SCOPE_MEMORY_MARKER)]


@pytest.mark.asyncio
async def test_sync_enabled_kbs_writes_managed_bullet(monkeypatch) -> None:
    calls: list[tuple] = []

    class _Repo:
        async def remove_lines(self, user_id, memory_scope, *, match, also_search_user_scope=False, agent_id_for_user=None):
            calls.append(("remove", match))
            return []

        async def append_lines(self, user_id, memory_scope, lines, *, source):
            calls.append(("append", lines, source))
            return object(), lines

    monkeypatch.setattr(
        "app.platform.integrations.kb_preference.MemoryRepository",
        lambda db: _Repo(),
    )

    async def _list(*, api_key: str):
        return [
            {"id": "a", "name": "CorpService"},
            {"id": "b", "name": "LRQ"},
            {"id": "c", "name": "HF Proposal"},
        ]

    monkeypatch.setattr(
        "app.platform.integrations.kb_preference.list_visible_knowledge_bases",
        _list,
    )

    await sync_enabled_kbs_to_agent_memory(
        object(),  # type: ignore[arg-type]
        user_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        disabled_kb_ids=["a", "c"],
        api_key="okf_test",
    )
    assert calls[0] == ("remove", KB_SCOPE_MEMORY_MARKER)
    assert calls[1][0] == "append"
    assert calls[1][2] == "kb-preferences"
    line = calls[1][1][0]
    assert "LRQ (b)" in line
    assert "CorpService" not in line
    assert "HF Proposal" not in line


@pytest.mark.asyncio
async def test_sync_enabled_kbs_skips_write_without_api_key(monkeypatch) -> None:
    class _Repo:
        async def remove_lines(self, *args, **kwargs):
            raise AssertionError("should not touch memory without api key when disabled set")

        async def append_lines(self, *args, **kwargs):
            raise AssertionError("should not append")

    monkeypatch.setattr(
        "app.platform.integrations.kb_preference.MemoryRepository",
        lambda db: _Repo(),
    )

    await sync_enabled_kbs_to_agent_memory(
        object(),  # type: ignore[arg-type]
        user_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        disabled_kb_ids=["a"],
        api_key=None,
    )
