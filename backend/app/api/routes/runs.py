import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.platform.current_user import get_current_user
from app.runs.manager import get_run_manager

router = APIRouter(prefix="/runs", tags=["runs"])


class RunCancelOut(BaseModel):
    run_id: uuid.UUID
    chat_id: uuid.UUID
    status: str


@router.post("/{run_id}/cancel", response_model=RunCancelOut)
async def cancel_run(
    run_id: uuid.UUID,
    _user=Depends(get_current_user),
) -> RunCancelOut:
    run = await get_run_manager().cancel(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found or not active")
    return RunCancelOut(run_id=run.run_id, chat_id=run.chat_id, status=run.status.value)
