"""Ephemeral MAF agent runs — isolated from parent chat history."""

from __future__ import annotations

from agent_framework import Agent, Message

from app.config import Settings, get_settings
from app.platform.llm.model_catalog import ModelEntry, get_model_catalog, is_provider_configured
from app.platform.llm.model_registry import ModelProvider, ModelProviderRegistry


def resolve_vision_model_entry(
    *,
    model_id: str | None = None,
    settings: Settings | None = None,
) -> ModelEntry:
    """Pick a vision-capable catalog model for attachment mini-requests."""
    s = settings or get_settings()
    catalog = get_model_catalog()
    candidates: list[str] = []
    if model_id:
        candidates.append(model_id)
    configured = (s.attachment_vision_model_id or "").strip()
    if configured:
        candidates.append(configured)
    candidates.extend(
        [
            "qwen-vl-max",
            "qwen3.7-plus",
            "qwen3.8-max",
            "gpt-5.4",
            "claude-sonnet-4-6",
            "deepseek-flash",
        ]
    )
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        entry = catalog.get(candidate)
        if entry is None or not entry.enabled or not entry.deployment.strip():
            continue
        if is_provider_configured(entry.provider, s):
            return entry
    available = catalog.list_available(s)
    if not available:
        raise ValueError("No configured vision model is available in the model catalog.")
    return available[0]


async def ephemeral_vision_run(
    *,
    instructions: str,
    user_message: Message,
    model_id: str | None = None,
    settings: Settings | None = None,
) -> str:
    """Run a one-off vision agent with empty history (not persisted to parent chat)."""
    s = settings or get_settings()
    entry = resolve_vision_model_entry(model_id=model_id, settings=s)
    registry = ModelProviderRegistry(s)
    agent = registry.create_agent(
        name="attachment-vision-worker",
        instructions=instructions,
        model_provider=ModelProvider(entry.provider),
        model_name=entry.deployment,
        context_providers=None,
        middleware=None,
        tools=None,
        require_per_service_call_history_persistence=False,
    )
    result = await agent.run(user_message)
    return (result.text or "").strip()


def resolve_map_text_model_entry(
    *,
    model_id: str | None = None,
    settings: Settings | None = None,
) -> ModelEntry:
    """Pick a text model for attachment map / summarize workers."""
    s = settings or get_settings()
    catalog = get_model_catalog()
    candidates: list[str] = []
    if model_id:
        candidates.append(model_id)
    candidates.extend(["qwen3.7-plus", "deepseek-flash", "gpt-5.4", "claude-sonnet-4-6"])
    seen: set[str] = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        entry = catalog.get(candidate)
        if entry is None or not entry.enabled or not entry.deployment.strip():
            continue
        if is_provider_configured(entry.provider, s):
            return entry
    available = catalog.list_available(s)
    if not available:
        raise ValueError("No configured text model is available for attachment map workers.")
    return available[0]


async def ephemeral_text_run(
    *,
    instructions: str,
    prompt: str,
    model_id: str | None = None,
    settings: Settings | None = None,
) -> str:
    """Run a one-off text-only worker (no parent chat history)."""
    s = settings or get_settings()
    entry = resolve_map_text_model_entry(model_id=model_id, settings=s)
    registry = ModelProviderRegistry(s)
    agent = registry.create_agent(
        name="attachment-map-worker",
        instructions=instructions,
        model_provider=ModelProvider(entry.provider),
        model_name=entry.deployment,
        context_providers=None,
        middleware=None,
        tools=None,
        require_per_service_call_history_persistence=False,
    )
    result = await agent.run(prompt)
    return (result.text or "").strip()
