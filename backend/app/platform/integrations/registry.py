from __future__ import annotations

from app.platform.integrations.providers.hubspot import HubSpotIntegrationProvider
from app.platform.integrations.providers.notion import NotionIntegrationProvider
from app.platform.integrations.types import IntegrationOAuthProvider

_PROVIDERS: dict[str, IntegrationOAuthProvider] = {
    NotionIntegrationProvider.id: NotionIntegrationProvider(),
    HubSpotIntegrationProvider.id: HubSpotIntegrationProvider(),
}


def get_integration_provider(provider_id: str) -> IntegrationOAuthProvider | None:
    return _PROVIDERS.get(provider_id.strip().lower())


def list_integration_providers() -> list[IntegrationOAuthProvider]:
    return list(_PROVIDERS.values())
