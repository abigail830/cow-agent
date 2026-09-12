from __future__ import annotations

from app.config import Settings, get_settings

ZHIPU_WEB_SEARCH_PROVIDER_ID = "zhipu-web-search"


class ZhipuWebSearchIntegrationProvider:
    """Per-user Zhipu API key for the web search MCP."""

    id = ZHIPU_WEB_SEARCH_PROVIDER_ID
    auth_kind = "api_key"
    display_name = "Zhipu Web Search"
    description = "Your Zhipu API key for web search in Content Studio KB Q&A."
    mcp_url = None

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def is_platform_configured(self) -> bool:
        url = (self._settings.zhipu_web_search_mcp_url or "").strip()
        return bool(url)

    @staticmethod
    def mask_api_key_label(api_key: str) -> str:
        trimmed = api_key.strip()
        if len(trimmed) <= 4:
            return "••••"
        return f"••••{trimmed[-4:]}"
