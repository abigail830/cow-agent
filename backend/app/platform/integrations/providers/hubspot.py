from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings, get_settings
from app.platform.integrations.types import OAuthTokenBundle

logger = logging.getLogger(__name__)

HUBSPOT_PROVIDER_ID = "hubspot"
HUBSPOT_MCP_URL = "https://mcp.hubspot.com"
HUBSPOT_RESOURCE = "https://mcp.hubspot.com"
HUBSPOT_AUTHORIZE_URL = "https://mcp.hubspot.com/oauth/authorize"
HUBSPOT_TOKEN_URL = "https://mcp.hubspot.com/oauth/v3/token"


class HubSpotIntegrationProvider:
    """Stub-ready provider mirroring the ascentium-omni HubSpot MCP OAuth shape."""

    id = HUBSPOT_PROVIDER_ID
    display_name = "HubSpot"
    description = "Connect HubSpot CRM via remote MCP (OAuth)."
    mcp_url = HUBSPOT_MCP_URL

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def is_platform_configured(self) -> bool:
        return bool(
            self._settings.hubspot_mcp_client_id
            and self._settings.hubspot_mcp_client_secret
            and self._settings.hubspot_mcp_redirect_uri
        )

    def resource(self) -> str:
        return HUBSPOT_RESOURCE

    def build_authorize_url(self, *, state: str, code_challenge: str) -> str:
        client_id = self._settings.hubspot_mcp_client_id
        redirect_uri = self._settings.hubspot_mcp_redirect_uri
        if not client_id or not redirect_uri:
            raise ValueError("HubSpot MCP OAuth is not configured")

        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "resource": self.resource(),
        }
        return f"{HUBSPOT_AUTHORIZE_URL}?{urlencode(params)}"

    async def exchange_code(self, *, code: str, code_verifier: str) -> OAuthTokenBundle:
        body = await self._post_token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._settings.hubspot_mcp_redirect_uri or "",
                "code_verifier": code_verifier,
            }
        )
        return self._bundle_from_response(body)

    async def refresh_access_token(self, *, refresh_token: str) -> OAuthTokenBundle:
        body = await self._post_token(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            require_refresh_token=False,
        )
        return self._bundle_from_response(body, fallback_refresh_token=refresh_token)

    async def _post_token(
        self,
        payload: dict[str, str],
        *,
        require_refresh_token: bool = True,
    ) -> dict[str, Any]:
        client_id = self._settings.hubspot_mcp_client_id
        client_secret = self._settings.hubspot_mcp_client_secret
        if not client_id or not client_secret:
            raise ValueError("HubSpot MCP OAuth is not configured")

        form = {
            **payload,
            "client_id": client_id,
            "client_secret": client_secret,
            "resource": self.resource(),
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                HUBSPOT_TOKEN_URL,
                data=form,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        data = response.json() if response.content else {}
        if not response.is_success:
            detail = data.get("message") or data.get("error") or response.text
            raise ValueError(f"HubSpot token request failed ({response.status_code}): {detail}")

        if not data.get("access_token"):
            raise ValueError("HubSpot token response missing access_token")
        if require_refresh_token and not data.get("refresh_token"):
            raise ValueError("HubSpot token response missing refresh_token")

        return data

    @staticmethod
    def _bundle_from_response(
        body: dict[str, Any],
        *,
        fallback_refresh_token: str | None = None,
    ) -> OAuthTokenBundle:
        expires_in = body.get("expires_in")
        seconds = int(expires_in) if isinstance(expires_in, (int, float)) else 1800
        refresh_token = body.get("refresh_token") or fallback_refresh_token
        return OAuthTokenBundle(
            access_token=str(body["access_token"]),
            refresh_token=str(refresh_token) if refresh_token else None,
            expires_at_ms=int(time.time() * 1000) + seconds * 1000,
            scopes=[],
            account_label=None,
            metadata={"portal_id": body.get("hub_id")} if body.get("hub_id") else None,
        )
