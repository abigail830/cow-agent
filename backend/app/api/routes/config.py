from fastapi import APIRouter, Depends

from app.config import get_settings
from app.platform.attachment_limits import attachment_limits_dict
from app.platform.current_user import get_current_user

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/attachments")
async def get_attachment_config(
    _user=Depends(get_current_user),
) -> dict[str, int]:
    """Platform-wide attachment limits (from .env, shared by all agents)."""
    return attachment_limits_dict(get_settings())
