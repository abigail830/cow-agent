"""Ephemeral MAF agent runs — isolated from parent chat history."""

from __future__ import annotations

from agent_framework import Agent, Message

from app.config import Settings, get_settings
from app.platform.llm.model_catalog import (
    MODEL_ROLE_CHAT,
    MODEL_ROLE_TEXT_WORKER,
    MODEL_ROLE_VISION_WORKER,
    ModelEntry,
    get_model_catalog,
    is_provider_configured,
)
from app.platform.llm.model_registry import ModelProvider, ModelProviderRegistry


def _entry_usable(entry: ModelEntry | None, *, settings: Settings) -> bool:
    if entry is None or not entry.enabled or not entry.deployment.strip():
        return False
    return is_provider_configured(entry.provider, settings)


def resolve_worker_model_entry(
    *,
    role: str,
    settings: Settings | None = None,
    model_id: str | None = None,
    env_model_id: str | None = None,
    fallback_role: str | None = None,
) -> ModelEntry:
    """Resolve a catalog model for an ephemeral worker by role."""
    s = settings or get_settings()
    catalog = get_model_catalog()
    for candidate in (model_id, (env_model_id or "").strip() or None):
        if not candidate:
            continue
        entry = catalog.get(candidate)
        if _entry_usable(entry, settings=s) and entry is not None and entry.has_role(role):
            return entry

    workers = catalog.list_for_role(role, s)
    if workers:
        return workers[0]

    if fallback_role and fallback_role != role:
        fallback_workers = catalog.list_for_role(fallback_role, s)
        if fallback_workers:
            return fallback_workers[0]

    raise ValueError(f"No configured catalog model is available for role '{role}'.")


def resolve_vision_model_entry(
    *,
    model_id: str | None = None,
    settings: Settings | None = None,
) -> ModelEntry:
    """Pick a vision-worker catalog model for attachment mini-requests."""
    s = settings or get_settings()
    return resolve_worker_model_entry(
        role=MODEL_ROLE_VISION_WORKER,
        settings=s,
        model_id=model_id,
        env_model_id=s.attachment_vision_model_id,
    )


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
    return resolve_worker_model_entry(
        role=MODEL_ROLE_TEXT_WORKER,
        settings=s,
        model_id=model_id,
        fallback_role=MODEL_ROLE_CHAT,
    )


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
