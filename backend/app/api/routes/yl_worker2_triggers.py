"""yl-worker2 external event triggers (Webhook + new Session)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.platform.current_user import get_current_user_id
from app.platform.platform_sync import agent_id_for_slug
from app.yl_worker2.triggers.handler import AGENT_SLUG, handle_yl_worker2_trigger
from app.yl_worker2.triggers.schemas import YlWorker2TriggerPayload, YlWorker2TriggerResponse

router = APIRouter(prefix="/agents", tags=["yl-worker2-triggers"])


@router.post(
    "/yl-worker2/triggers",
    response_model=YlWorker2TriggerResponse,
    status_code=201,
)
async def post_yl_worker2_trigger(
    body: YlWorker2TriggerPayload,
    auto_run: bool = Query(
        True,
        description="If true (default), persist initial message and run agent synchronously.",
    ),
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> YlWorker2TriggerResponse:
    """Webhook entry: external system event → new chat session."""
    _ = agent_id_for_slug(AGENT_SLUG)
    try:
        return await handle_yl_worker2_trigger(
            db,
            body,
            user_id=user_id,
            auto_run=auto_run,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
