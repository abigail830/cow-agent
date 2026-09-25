from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlencode

import httpx

from app.config import Settings, get_settings
from app.platform.integrations.types import OAuthTokenBundle

logger = logging.getLogger(__name__)

FEISHU_PROVIDER_ID = "feishu"
DEFAULT_FEISHU_API_BASE = "https://open.feishu.cn"
DEFAULT_FEISHU_OAUTH_SCOPE = (
    "offline_access im:message:readonly docx:document:readonly calendar:calendar:readonly"
)


class FeishuIntegrationProvider:
    id = FEISHU_PROVIDER_ID
    auth_kind = "oauth"
    display_name = "Feishu"
    description = "Connect Feishu to read messages, docs, and calendar via Open Platform APIs."
    mcp_url = None

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def is_platform_configured(self) -> bool:
        return bool(
            self._settings.feishu_app_id
            and self._settings.feishu_app_secret
            and self._settings.feishu_oauth_redirect_uri
        )

    def resource(self) -> str:
        return self._api_base()

    def build_authorize_url(self, *, state: str, code_challenge: str) -> str:
        del code_challenge  # Feishu web OAuth uses client_secret; PKCE is not required.
        client_id = self._settings.feishu_app_id
        redirect_uri = self._settings.feishu_oauth_redirect_uri
        if not client_id or not redirect_uri:
            raise ValueError("Feishu OAuth is not configured")

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": self._oauth_scope(),
        }
        return f"{self._authorize_base()}/open-apis/authen/v1/authorize?{urlencode(params)}"

    async def exchange_code(self, *, code: str, code_verifier: str) -> OAuthTokenBundle:
        del code_verifier
        body = await self._post_token(
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self._settings.feishu_oauth_redirect_uri or "",
            }
        )
        bundle = self._bundle_from_response(body)
        account_label = await self._fetch_account_label(bundle.access_token)
        if account_label:
            return OAuthTokenBundle(
                access_token=bundle.access_token,
                refresh_token=bundle.refresh_token,
                expires_at_ms=bundle.expires_at_ms,
                scopes=bundle.scopes,
                account_label=account_label,
                metadata=bundle.metadata,
            )
        return bundle

    async def refresh_access_token(self, *, refresh_token: str) -> OAuthTokenBundle:
        body = await self._post_token(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            require_refresh_token=False,
        )
        return self._bundle_from_response(body, fallback_refresh_token=refresh_token)

    def _oauth_scope(self) -> str:
        configured = (self._settings.feishu_oauth_scope or "").strip()
        return configured or DEFAULT_FEISHU_OAUTH_SCOPE

    def _api_base(self) -> str:
        configured = (self._settings.feishu_api_base or "").strip().rstrip("/")
        return configured or DEFAULT_FEISHU_API_BASE

    def _authorize_base(self) -> str:
        configured = (self._settings.feishu_oauth_authorize_base or "").strip().rstrip("/")
        return configured or "https://accounts.feishu.cn"

    def _token_url(self) -> str:
        return f"{self._api_base()}/open-apis/authen/v2/oauth/token"

    async def _post_token(
        self,
        payload: dict[str, str],
        *,
        require_refresh_token: bool = True,
    ) -> dict[str, Any]:
        client_id = self._settings.feishu_app_id
        client_secret = self._settings.feishu_app_secret
        if not client_id or not client_secret:
            raise ValueError("Feishu OAuth is not configured")

        body = {
            **payload,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self._token_url(),
                json=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )

        data = response.json() if response.content else {}
        if not response.is_success or data.get("code") not in (0, None):
            detail = data.get("msg") or data.get("error_description") or data.get("error") or response.text
            raise ValueError(f"Feishu token request failed ({response.status_code}): {detail}")

        access_token = data.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise ValueError("Feishu token response missing access_token")
        if require_refresh_token and not data.get("refresh_token"):
            raise ValueError("Feishu token response missing refresh_token")

        return data

    async def _fetch_account_label(self, access_token: str) -> str | None:
        url = f"{self._api_base()}/open-apis/authen/v1/user_info"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
            payload = response.json() if response.content else {}
        except Exception:
            logger.exception("Failed to fetch Feishu user_info")
            return None
        if payload.get("code") != 0:
            return None
        data = payload.get("data") or {}
        if not isinstance(data, dict):
            return None
        for key in ("email", "name", "en_name"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    @staticmethod
    def _bundle_from_response(
        body: dict[str, Any],
        *,
        fallback_refresh_token: str | None = None,
    ) -> OAuthTokenBundle:
        expires_in = body.get("expires_in")
        seconds = int(expires_in) if isinstance(expires_in, (int, float)) else 7200
        refresh_token = body.get("refresh_token") or fallback_refresh_token
        scope_raw = body.get("scope") or ""
        scopes = [part.strip() for part in str(scope_raw).split() if part.strip()]
        metadata: dict[str, Any] = {}
        refresh_expires = body.get("refresh_token_expires_in")
        if isinstance(refresh_expires, (int, float)):
            metadata["refresh_token_expires_in"] = int(refresh_expires)

        return OAuthTokenBundle(
            access_token=str(body["access_token"]),
            refresh_token=str(refresh_token) if refresh_token else None,
            expires_at_ms=int(time.time() * 1000) + seconds * 1000,
            scopes=scopes,
            account_label=None,
            metadata=metadata or None,
        )


def feishu_document_id_from_url(url: str) -> str | None:
    trimmed = url.strip()
    if not trimmed:
        return None
    if "/docx/" in trimmed:
        segment = trimmed.split("/docx/", 1)[1].split("/", 1)[0].split("?", 1)[0]
        return segment or None
    if trimmed.startswith("dox"):
        return trimmed
    return None
