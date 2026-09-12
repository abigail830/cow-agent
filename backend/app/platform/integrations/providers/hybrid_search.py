from __future__ import annotations

from app.config import Settings, get_settings

HYBRID_SEARCH_PROVIDER_ID = "hybrid-search"


class HybridSearchIntegrationProvider:
    """Per-user API key for the hybrid-search MCP (one key scopes one user's KB access)."""

    id = HYBRID_SEARCH_PROVIDER_ID
    auth_kind = "api_key"
    display_name = "Hybrid Search"
    description = "Your knowledge-base search API key. Required for KB Q&A in Content Studio."
    mcp_url = None

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def is_platform_configured(self) -> bool:
        url = (self._settings.hybrid_search_mcp_url or "").strip()
        return bool(url)

    @staticmethod
    def mask_api_key_label(api_key: str) -> str:
        trimmed = api_key.strip()
        if len(trimmed) <= 4:
            return "••••"
        return f"••••{trimmed[-4:]}"
