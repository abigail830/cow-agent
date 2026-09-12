from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.repositories.user_integrations import UserIntegrationRepository
from app.platform.auth.secret_store import SecretStoreError
from app.platform.integrations.oauth.pkce import (
    create_oauth_state,
    generate_code_challenge,
    generate_code_verifier,
)
from app.platform.integrations.registry import get_integration_provider, list_integration_providers
from app.platform.integrations.token_service import IntegrationTokenService
from app.platform.integrations.types import IntegrationPublicStatus


def _oauth_signing_key() -> str:
    key = get_settings().mcp_secrets_key
    if not key:
        raise SecretStoreError(
            "MCP_SECRETS_KEY is not configured. Generate one with: "
            'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
        )
    return key


class IntegrationService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._repo = UserIntegrationRepository(db)
        self._tokens = IntegrationTokenService(db)

    async def list_statuses(self, user_id: uuid.UUID) -> list[IntegrationPublicStatus]:
        rows = {row.provider: row for row in await self._repo.list_for_user(user_id)}
        statuses: list[IntegrationPublicStatus] = []
        for provider in list_integration_providers():
            row = rows.get(provider.id)
            connected = bool(row and row.status == "connected" and row.secrets_encrypted)
            token_valid = False
            if connected:
                token = await self._tokens.get_valid_access_token(user_id=user_id, provider=provider.id)
                token_valid = token is not None
            statuses.append(
                IntegrationPublicStatus(
                    provider=provider.id,
                    display_name=provider.display_name,
                    description=provider.description,
                    configured=provider.is_platform_configured(),
                    connected=connected and token_valid,
                    account_label=row.account_label if row else None,
                    token_valid=token_valid,
                )
            )
        return statuses

    async def begin_oauth(self, *, user_id: uuid.UUID, provider_id: str) -> str:
        provider = get_integration_provider(provider_id)
        if provider is None:
            raise ValueError(f"Unknown integration provider: {provider_id}")
        if not provider.is_platform_configured():
            raise ValueError(f"{provider.display_name} OAuth is not configured on this deployment")

        code_verifier = generate_code_verifier()
        code_challenge = generate_code_challenge(code_verifier)
        state = create_oauth_state(
            user_id=str(user_id),
            provider=provider.id,
            code_verifier=code_verifier,
            signing_key=_oauth_signing_key(),
        )
        return provider.build_authorize_url(state=state, code_challenge=code_challenge)

    async def complete_oauth(
        self,
        *,
        provider_id: str,
        code: str,
        state: str,
    ) -> uuid.UUID:
        from app.platform.integrations.oauth.pkce import consume_oauth_state

        pending = consume_oauth_state(state, signing_key=_oauth_signing_key())
        if pending is None or pending.provider != provider_id:
            raise ValueError("Invalid or expired OAuth state")

        provider = get_integration_provider(provider_id)
        if provider is None:
            raise ValueError(f"Unknown integration provider: {provider_id}")

        bundle = await provider.exchange_code(code=code, code_verifier=pending.code_verifier)
        user_id = uuid.UUID(pending.user_id)
        await self._tokens.save_tokens(user_id=user_id, provider=provider.id, bundle=bundle)
        return user_id

    async def disconnect(self, *, user_id: uuid.UUID, provider_id: str) -> bool:
        provider = get_integration_provider(provider_id)
        if provider is None:
            raise ValueError(f"Unknown integration provider: {provider_id}")
        return await self._tokens.disconnect(user_id=user_id, provider=provider.id)
