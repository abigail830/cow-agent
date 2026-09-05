from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import Settings, get_settings
from app.platform.agent.profile_loader import _resolve_env
from app.platform.llm.model_registry import ModelProvider

_CATALOG_PATH = Path(__file__).resolve().parents[3] / "config" / "models.yaml"


@dataclass(frozen=True)
class ModelEntry:
    id: str
    label: str
    provider: str
    deployment: str
    enabled: bool = True

    @property
    def supports_attachments(self) -> bool:
        return self.provider not in {
            ModelProvider.SILICONFLOW.value,
            ModelProvider.DASHSCOPE.value,
            ModelProvider.DEEPSEEK.value,
        }


@dataclass(frozen=True)
class ModelCatalog:
    models: dict[str, ModelEntry]
    providers: dict[str, dict[str, str]]

    def get(self, model_id: str | None) -> ModelEntry | None:
        if not model_id:
            return None
        return self.models.get(model_id)

    def list_enabled(self) -> list[ModelEntry]:
        return [entry for entry in self.models.values() if entry.enabled]

    def list_available(self, settings: Settings | None = None) -> list[ModelEntry]:
        s = settings or get_settings()
        available: list[ModelEntry] = []
        for entry in self.list_enabled():
            if not entry.deployment.strip():
                continue
            if _provider_configured(entry.provider, s):
                available.append(entry)
        return sorted(available, key=lambda item: item.label.lower())

    def find_by_provider_deployment(self, provider: str, deployment: str) -> ModelEntry | None:
        provider = str(provider or "").strip()
        deployment = str(deployment or "").strip()
        if not provider or not deployment:
            return None
        for entry in self.models.values():
            if entry.provider == provider and entry.deployment == deployment:
                return entry
        return None

    def resolve_default_model_id(
        self,
        *,
        default_model: str | None,
        model_provider: str,
        model_name: str,
    ) -> str | None:
        if default_model:
            entry = self.get(default_model)
            if entry is not None:
                return entry.id
        matched = self.find_by_provider_deployment(model_provider, model_name)
        if matched is not None:
            return matched.id
        if default_model and default_model in self.models:
            return default_model
        return None


def _provider_configured(provider: str, settings: Settings) -> bool:
    if provider == ModelProvider.AZURE_OPENAI.value:
        return bool(settings.azure_api_key and settings.azure_openai_base_url)
    if provider == ModelProvider.AZURE_ANTHROPIC.value:
        return bool(settings.claude_azure_api_key and settings.claude_azure_foundry_endpoint)
    if provider == ModelProvider.SILICONFLOW.value:
        return bool(settings.siliconflow_api_key)
    if provider == ModelProvider.DASHSCOPE.value:
        return bool(settings.dashscope_api_key)
    if provider == ModelProvider.DEEPSEEK.value:
        return bool(settings.deepseek_api_key)
    return False


def is_provider_configured(provider: str, settings: Settings | None = None) -> bool:
    return _provider_configured(provider, settings or get_settings())


def _load_catalog_from_disk() -> ModelCatalog:
    if not _CATALOG_PATH.exists():
        raise FileNotFoundError(f"Model catalog not found: {_CATALOG_PATH}")
    raw = yaml.safe_load(_CATALOG_PATH.read_text(encoding="utf-8")) or {}
    providers_raw = raw.get("providers") or {}
    providers: dict[str, dict[str, str]] = {}
    if isinstance(providers_raw, dict):
        for name, cfg in providers_raw.items():
            if isinstance(cfg, dict):
                providers[str(name)] = {k: _resolve_env(str(v)) for k, v in cfg.items()}

    models: dict[str, ModelEntry] = {}
    for item in raw.get("models") or []:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            continue
        models[model_id] = ModelEntry(
            id=model_id,
            label=str(item.get("label") or model_id),
            provider=str(item.get("provider") or ""),
            deployment=_resolve_env(str(item.get("deployment") or "")),
            enabled=bool(item.get("enabled", True)),
        )
    return ModelCatalog(models=models, providers=providers)


@lru_cache
def get_model_catalog() -> ModelCatalog:
    return _load_catalog_from_disk()


def reload_model_catalog() -> ModelCatalog:
    get_model_catalog.cache_clear()
    return get_model_catalog()


def resolve_agent_model(
    agent_row: Any,
    model_id: str | None = None,
) -> ModelEntry:
    catalog = get_model_catalog()
    for candidate in (
        model_id,
        getattr(agent_row, "default_model_id", None),
    ):
        entry = catalog.get(candidate)
        if entry is not None:
            return entry
    matched = catalog.find_by_provider_deployment(
        getattr(agent_row, "model_provider", ""),
        getattr(agent_row, "model_name", ""),
    )
    if matched is not None:
        return matched
    provider = str(getattr(agent_row, "model_provider", "") or "").strip()
    deployment = str(getattr(agent_row, "model_name", "") or "").strip()
    if provider and deployment:
        return ModelEntry(
            id=deployment,
            label=deployment,
            provider=provider,
            deployment=deployment,
        )
    raise ValueError(
        f"No catalog model matches agent {getattr(agent_row, 'slug', agent_row)} "
        f"(provider={getattr(agent_row, 'model_provider', None)!r}, "
        f"model={getattr(agent_row, 'model_name', None)!r}, preference={model_id!r})"
    )
