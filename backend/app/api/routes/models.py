from fastapi import APIRouter, Depends

from app.api.schemas import ModelOut
from app.platform.auth.current_user import get_current_user
from app.platform.llm.model_catalog import get_model_catalog

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelOut])
async def list_models(_user=Depends(get_current_user)) -> list[ModelOut]:
    catalog = get_model_catalog()
    return [
        ModelOut(
            id=entry.id,
            label=entry.label,
            provider=entry.provider,
            supports_attachments=entry.supports_attachments,
        )
        for entry in catalog.list_available()
    ]
