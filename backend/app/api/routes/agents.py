import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import AgentModelSelectionIn, AgentOut
from app.db.models import AgentModel, User
from app.db.session import get_db
from app.platform.auth.current_user import get_current_user
from app.platform.agent.profile_loader import discover_agent_profiles
from app.platform.llm.model_catalog import get_model_catalog
from app.platform.llm.model_preference import get_model_preference, set_model_preference

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=list[AgentOut])
async def list_agents(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AgentOut]:
    active_slugs = {p.slug for p in discover_agent_profiles()}
    result = await db.execute(
        select(AgentModel)
        .where(AgentModel.slug.isnot(None), AgentModel.slug.in_(active_slugs))
        .order_by(AgentModel.name)
    )
    agents = result.scalars().all()
    return [await _to_out(agent, user.id) for agent in agents]


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentOut:
    agent = await db.get(AgentModel, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return await _to_out(agent, user.id)


@router.patch("/{agent_id}/model-selection", response_model=AgentOut)
async def patch_agent_model_selection(
    agent_id: uuid.UUID,
    body: AgentModelSelectionIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentOut:
    agent = await db.get(AgentModel, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    catalog = get_model_catalog()
    available_ids = {item.id for item in catalog.list_available()}
    entry = catalog.get(body.model_id)
    if entry is None or body.model_id not in available_ids:
        raise HTTPException(status_code=400, detail=f"Unknown or unavailable model: {body.model_id}")
    await set_model_preference(user.id, agent_id, body.model_id)
    return await _to_out(agent, user.id)


async def _to_out(agent: AgentModel, user_id: uuid.UUID) -> AgentOut:
    selected = await get_model_preference(user_id, agent.id)
    return AgentOut(
        id=agent.id,
        slug=agent.slug,
        name=agent.name,
        description=agent.description,
        model_provider=agent.model_provider,
        model_name=agent.model_name,
        default_model_id=agent.default_model_id,
        selected_model_id=selected or agent.default_model_id,
    )
