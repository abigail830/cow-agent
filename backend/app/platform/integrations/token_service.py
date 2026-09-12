"""Encrypt, refresh, and resolve per-user integration credentials for MCP servers."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.user_integrations import UserIntegrationRepository
from app.platform.auth.secret_store import SecretStoreError, decrypt_secrets, encrypt_secrets
from app.platform.integrations.registry import get_integration_provider, integration_auth_kind
from app.platform.integrations.types import OAuthTokenBundle

logger = logging.getLogger(__name__)

_REFRESH_SKEW_MS = 60_000
_refresh_flights: dict[str, asyncio.Task[OAuthTokenBundle | None]] = {}


@dataclass(frozen=True)
class StoredIntegrationTokens:
    access_token: str
    refresh_token: str | None
    expires_at_ms: int
    scopes: list[str]
    account_label: str | None = None
    metadata: dict[str, Any] | None = None


def _tokens_to_secret(bundle: OAuthTokenBundle) -> dict[str, Any]:
    return {
        "access_token": bundle.access_token,
        "refresh_token": bundle.refresh_token,
        "expires_at_ms": bundle.expires_at_ms,
        "scopes": bundle.scopes,
        "account_label": bundle.account_label,
        "metadata": bundle.metadata or {},
    }


def _secret_to_tokens(payload: dict[str, Any]) -> StoredIntegrationTokens | None:
    access_token = payload.get("access_token")
    expires_at_ms = payload.get("expires_at_ms")
    if not isinstance(access_token, str) or not access_token:
        return None
    if not isinstance(expires_at_ms, (int, float)):
        return None
    refresh_token = payload.get("refresh_token")
    scopes = payload.get("scopes") or []
    account_label = payload.get("account_label")
    metadata = payload.get("metadata") or {}
    return StoredIntegrationTokens(
        access_token=access_token,
        refresh_token=str(refresh_token) if refresh_token else None,
        expires_at_ms=int(expires_at_ms),
        scopes=[str(item) for item in scopes] if isinstance(scopes, list) else [],
        account_label=str(account_label) if isinstance(account_label, str) else None,
        metadata=dict(metadata) if isinstance(metadata, dict) else {},
    )


class IntegrationTokenService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = UserIntegrationRepository(db)

    async def save_tokens(
        self,
        *,
        user_id: uuid.UUID,
        provider: str,
        bundle: OAuthTokenBundle,
    ) -> None:
        encrypted = encrypt_secrets(_tokens_to_secret(bundle))
        await self._repo.upsert_connected(
            user_id=user_id,
            provider=provider,
            secrets_encrypted=encrypted,
            account_label=bundle.account_label,
            integration_metadata=bundle.metadata,
        )
        await self._db.commit()

    async def save_api_key(
        self,
        *,
        user_id: uuid.UUID,
        provider: str,
        api_key: str,
        account_label: str | None = None,
    ) -> None:
        trimmed = api_key.strip()
        if not trimmed:
            raise ValueError("API key is required")
        bundle = OAuthTokenBundle(
            access_token=trimmed,
            refresh_token=None,
            expires_at_ms=4_102_444_800_000,
            scopes=[],
            account_label=account_label,
            metadata={"auth_kind": "api_key"},
        )
        await self.save_tokens(user_id=user_id, provider=provider, bundle=bundle)

    async def get_api_key(self, *, user_id: uuid.UUID, provider: str) -> str | None:
        if integration_auth_kind(provider) != "api_key":
            return None
        stored = await self.load_tokens(user_id=user_id, provider=provider)
        if stored is None:
            return None
        return stored.access_token

    async def get_mcp_bearer_token(
        self,
        *,
        user_id: uuid.UUID,
        provider: str,
        auth_kind: str,
    ) -> str | None:
        if auth_kind == "api_key":
            return await self.get_api_key(user_id=user_id, provider=provider)
        return await self.get_valid_access_token(user_id=user_id, provider=provider)

    async def disconnect(self, *, user_id: uuid.UUID, provider: str) -> bool:
        row = await self._repo.disconnect(user_id, provider)
        if row is None:
            return False
        await self._db.commit()
        return True

    async def load_tokens(self, *, user_id: uuid.UUID, provider: str) -> StoredIntegrationTokens | None:
        row = await self._repo.get(user_id, provider)
        if row is None or row.status != "connected" or not row.secrets_encrypted:
            return None
        try:
            payload = decrypt_secrets(row.secrets_encrypted)
        except SecretStoreError:
            logger.exception("Failed to decrypt integration tokens for %s/%s", user_id, provider)
            return None
        return _secret_to_tokens(payload)

    async def connection_version(self, *, user_id: uuid.UUID, provider: str) -> int:
        row = await self._repo.get(user_id, provider)
        if row is None:
            return 0
        return int(row.connection_version or 0)

    async def get_valid_access_token(self, *, user_id: uuid.UUID, provider: str) -> str | None:
        stored = await self.load_tokens(user_id=user_id, provider=provider)
        if stored is None:
            return None
        if stored.expires_at_ms - _REFRESH_SKEW_MS > int(time.time() * 1000):
            return stored.access_token
        refreshed = await self.refresh_access_token(user_id=user_id, provider=provider)
        return refreshed.access_token if refreshed else None

    async def refresh_access_token(
        self,
        *,
        user_id: uuid.UUID,
        provider: str,
    ) -> StoredIntegrationTokens | None:
        flight_key = f"{user_id}:{provider}"
        existing = _refresh_flights.get(flight_key)
        if existing is not None:
            result = await existing
            return result

        task = asyncio.create_task(self._refresh_once(user_id=user_id, provider=provider))
        _refresh_flights[flight_key] = task
        try:
            return await task
        finally:
            if _refresh_flights.get(flight_key) is task:
                _refresh_flights.pop(flight_key, None)

    async def _refresh_once(
        self,
        *,
        user_id: uuid.UUID,
        provider: str,
    ) -> StoredIntegrationTokens | None:
        stored = await self.load_tokens(user_id=user_id, provider=provider)
        if stored is None or not stored.refresh_token:
            return None

        oauth_provider = get_integration_provider(provider)
        if oauth_provider is None or getattr(oauth_provider, "auth_kind", "oauth") != "oauth":
            return None

        try:
            bundle = await oauth_provider.refresh_access_token(refresh_token=stored.refresh_token)
        except Exception:
            logger.exception("Integration token refresh failed for %s/%s", user_id, provider)
            return None

        merged = OAuthTokenBundle(
            access_token=bundle.access_token,
            refresh_token=bundle.refresh_token or stored.refresh_token,
            expires_at_ms=bundle.expires_at_ms,
            scopes=bundle.scopes or stored.scopes,
            account_label=bundle.account_label or stored.account_label,
            metadata={**(stored.metadata or {}), **(bundle.metadata or {})} or None,
        )
        await self.save_tokens(user_id=user_id, provider=provider, bundle=merged)
        return _secret_to_tokens(_tokens_to_secret(merged))
