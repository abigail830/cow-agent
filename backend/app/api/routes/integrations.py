from __future__ import annotations

import logging
from urllib.parse import urlencode, urlparse, urlunparse

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import User
from app.db.session import get_db
from app.platform.auth.current_user import get_current_user
from app.platform.integrations.registry import get_integration_provider
from app.platform.integrations.service import IntegrationService
from app.platform.mcp.mcp_pool import get_mcp_connection_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["integrations"])


class IntegrationStatusOut(BaseModel):
    provider: str
    display_name: str
    description: str
    auth_kind: str
    configured: bool
    connected: bool
    account_label: str | None = None
    token_valid: bool = False


class ConnectOut(BaseModel):
    authorize_url: str


class SaveCredentialsIn(BaseModel):
    api_key: str


class SaveCredentialsOut(BaseModel):
    connected: bool
    account_label: str | None = None


class DisconnectOut(BaseModel):
    disconnected: bool


def _integration_success_redirect(*, provider: str, status: str, error: str | None = None) -> str:
    settings = get_settings()
    base = settings.integration_success_redirect or settings.cors_origins[0]
    parsed = urlparse(base)
    path = parsed.path or "/"
    if path.endswith("/settings/integrations"):
        path = "/"
    query_params = {"integrations": "1", "provider": provider, "status": status}
    if error:
        query_params["error"] = error
    query = urlencode(query_params)
    return urlunparse(parsed._replace(path=path, query=query, fragment=""))


@router.get("", response_model=list[IntegrationStatusOut])
async def list_integrations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[IntegrationStatusOut]:
    service = IntegrationService(db)
    rows = await service.list_statuses(user.id)
    return [IntegrationStatusOut.model_validate(row.__dict__) for row in rows]


@router.post("/{provider_id}/connect", response_model=ConnectOut)
async def connect_integration(
    provider_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConnectOut:
    service = IntegrationService(db)
    try:
        authorize_url = await service.begin_oauth(user_id=user.id, provider_id=provider_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ConnectOut(authorize_url=authorize_url)


@router.put("/{provider_id}/credentials", response_model=SaveCredentialsOut)
async def save_integration_credentials(
    provider_id: str,
    body: SaveCredentialsIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SaveCredentialsOut:
    if get_integration_provider(provider_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown integration provider: {provider_id}")

    service = IntegrationService(db)
    try:
        account_label = await service.save_api_key(
            user_id=user.id,
            provider_id=provider_id,
            api_key=body.api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    await get_mcp_connection_pool().invalidate_user(user.id)
    return SaveCredentialsOut(connected=True, account_label=account_label)


@router.get("/{provider_id}/callback")
async def integration_oauth_callback(
    provider_id: str,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    if error:
        message = (error_description or error).replace("+", " ")
        return RedirectResponse(
            _integration_success_redirect(provider=provider_id, status="error", error=message),
            status_code=302,
        )
    if not code or not state:
        return RedirectResponse(
            _integration_success_redirect(provider=provider_id, status="error", error="Missing OAuth code or state"),
            status_code=302,
        )

    service = IntegrationService(db)
    try:
        user_id = await service.complete_oauth(provider_id=provider_id, code=code, state=state)
    except Exception as exc:
        logger.exception("Integration OAuth callback failed for %s", provider_id)
        message = str(exc)
        return RedirectResponse(
            _integration_success_redirect(provider=provider_id, status="error", error=message),
            status_code=302,
        )

    await get_mcp_connection_pool().invalidate_user(user_id)
    return RedirectResponse(
        _integration_success_redirect(provider=provider_id, status="connected"),
        status_code=302,
    )


@router.post("/{provider_id}/disconnect", response_model=DisconnectOut)
async def disconnect_integration(
    provider_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DisconnectOut:
    if get_integration_provider(provider_id) is None:
        raise HTTPException(status_code=404, detail=f"Unknown integration provider: {provider_id}")

    service = IntegrationService(db)
    disconnected = await service.disconnect(user_id=user.id, provider_id=provider_id)
    if disconnected:
        await get_mcp_connection_pool().invalidate_user(user.id)
    return DisconnectOut(disconnected=disconnected)
