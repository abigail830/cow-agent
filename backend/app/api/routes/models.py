from fastapi import APIRouter, Depends

from app.api.schemas import ModelOut
from app.platform.auth.current_user import get_current_user
from app.config import get_settings
from app.platform.llm.model_catalog import get_model_catalog, is_provider_configured

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelOut])
async def list_models(_user=Depends(get_current_user)) -> list[ModelOut]:
    catalog = get_model_catalog()
    settings = get_settings()
    entries = sorted(catalog.list_enabled(), key=lambda item: item.label.lower())
    return [
        ModelOut(
            id=entry.id,
            label=entry.label,
            provider=entry.provider,
            supports_attachments=entry.supports_attachments,
            available=is_provider_configured(entry.provider, settings)
            and bool(entry.deployment.strip()),
        )
        for entry in entries
        if entry.deployment.strip()
    ]
