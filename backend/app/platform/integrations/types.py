from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

IntegrationProviderId = Literal["notion", "hubspot"]
IntegrationStatus = Literal["connected", "disconnected"]


@dataclass(frozen=True)
class OAuthTokenBundle:
    access_token: str
    refresh_token: str | None
    expires_at_ms: int
    scopes: list[str]
    account_label: str | None = None
    metadata: dict | None = None


@dataclass(frozen=True)
class IntegrationPublicStatus:
    provider: str
    display_name: str
    description: str
    configured: bool
    connected: bool
    account_label: str | None = None
    token_valid: bool = False


class IntegrationOAuthProvider(Protocol):
    id: str
    display_name: str
    description: str
    mcp_url: str

    def is_platform_configured(self) -> bool: ...

    def resource(self) -> str: ...

    def build_authorize_url(self, *, state: str, code_challenge: str) -> str: ...

    async def exchange_code(self, *, code: str, code_verifier: str) -> OAuthTokenBundle: ...

    async def refresh_access_token(self, *, refresh_token: str) -> OAuthTokenBundle: ...
