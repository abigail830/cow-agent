from __future__ import annotations

from app.platform.integrations.providers.hybrid_search import HybridSearchIntegrationProvider
from app.platform.integrations.providers.hubspot import HubSpotIntegrationProvider
from app.platform.integrations.providers.notion import NotionIntegrationProvider
from app.platform.integrations.types import IntegrationApiKeyProvider, IntegrationAuthKind, IntegrationOAuthProvider

AnyIntegrationProvider = IntegrationOAuthProvider | IntegrationApiKeyProvider

_PROVIDERS: dict[str, AnyIntegrationProvider] = {
    NotionIntegrationProvider.id: NotionIntegrationProvider(),
    HubSpotIntegrationProvider.id: HubSpotIntegrationProvider(),
    HybridSearchIntegrationProvider.id: HybridSearchIntegrationProvider(),
}


def get_integration_provider(provider_id: str) -> AnyIntegrationProvider | None:
    return _PROVIDERS.get(provider_id.strip().lower())


def list_integration_providers() -> list[AnyIntegrationProvider]:
    return list(_PROVIDERS.values())


def integration_auth_kind(provider_id: str) -> IntegrationAuthKind | None:
    provider = get_integration_provider(provider_id)
    if provider is None:
        return None
    return provider.auth_kind
