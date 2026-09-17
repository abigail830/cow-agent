import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    AgentKbPreferenceIn,
    AgentKbPreferenceOut,
    AgentModelSelectionIn,
    AgentOut,
    KnowledgeBaseListOut,
    KnowledgeBaseOut,
)
from app.db.models import AgentModel, User
from app.db.session import get_db
from app.platform.auth.current_user import get_current_user
from app.platform.agent.profile_loader import discover_agent_profiles
from app.platform.integrations.kb_client import HybridSearchKbClientError, list_visible_knowledge_bases
from app.platform.integrations.kb_preference import (
    agent_supports_kb_scope,
    get_disabled_kb_ids,
    set_disabled_kb_ids,
)
from app.platform.integrations.providers.hybrid_search import HYBRID_SEARCH_PROVIDER_ID
from app.platform.integrations.token_service import IntegrationTokenService
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
    return [await _to_out(agent, user.id, db) for agent in agents]


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentOut:
    agent = await db.get(AgentModel, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return await _to_out(agent, user.id, db)


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
    await set_model_preference(db, user.id, agent_id, body.model_id)
    await db.commit()
    return await _to_out(agent, user.id, db)


@router.get("/{agent_id}/kb-preferences", response_model=AgentKbPreferenceOut)
async def get_agent_kb_preferences(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentKbPreferenceOut:
    agent = await db.get(AgentModel, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    disabled = await get_disabled_kb_ids(db, user.id, agent_id)
    return AgentKbPreferenceOut(disabled_kb_ids=disabled)


@router.put("/{agent_id}/kb-preferences", response_model=AgentKbPreferenceOut)
async def put_agent_kb_preferences(
    agent_id: uuid.UUID,
    body: AgentKbPreferenceIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AgentKbPreferenceOut:
    agent = await db.get(AgentModel, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if not agent_supports_kb_scope(agent.config if isinstance(agent.config, dict) else {}):
        raise HTTPException(status_code=400, detail="This agent does not use hybrid-search knowledge bases")
    disabled = await set_disabled_kb_ids(db, user.id, agent_id, body.disabled_kb_ids)
    await db.commit()
    return AgentKbPreferenceOut(disabled_kb_ids=disabled)


@router.get("/{agent_id}/knowledge-bases", response_model=KnowledgeBaseListOut)
async def list_agent_knowledge_bases(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> KnowledgeBaseListOut:
    agent = await db.get(AgentModel, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    if not agent_supports_kb_scope(agent.config if isinstance(agent.config, dict) else {}):
        return KnowledgeBaseListOut(
            connected=False,
            items=[],
            disabled_kb_ids=[],
            message="This agent does not use hybrid-search knowledge bases",
        )

    api_key = await IntegrationTokenService(db).get_api_key(
        user_id=user.id,
        provider=HYBRID_SEARCH_PROVIDER_ID,
    )
    disabled = await get_disabled_kb_ids(db, user.id, agent_id)
    if not api_key:
        return KnowledgeBaseListOut(
            connected=False,
            items=[],
            disabled_kb_ids=disabled,
            message="Connect Hybrid Search in Integrations to list knowledge bases",
        )

    try:
        raw_items = await list_visible_knowledge_bases(api_key=api_key)
    except HybridSearchKbClientError as exc:
        status = exc.status_code or 502
        if status in {401, 403}:
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    disabled_set = set(disabled)
    items = [
        KnowledgeBaseOut(
            id=str(item["id"]),
            name=str(item.get("name") or item["id"]),
            description=item.get("description"),
            type=item.get("type"),
            item_count=item.get("item_count") if isinstance(item.get("item_count"), int) else None,
            is_configured=item.get("is_configured") if isinstance(item.get("is_configured"), bool) else None,
            enabled=str(item["id"]) not in disabled_set,
        )
        for item in raw_items
    ]
    return KnowledgeBaseListOut(connected=True, items=items, disabled_kb_ids=disabled)


async def _to_out(agent: AgentModel, user_id: uuid.UUID, db: AsyncSession) -> AgentOut:
    selected = await get_model_preference(db, user_id, agent.id)
    return AgentOut(
        id=agent.id,
        slug=agent.slug,
        name=agent.name,
        description=agent.description,
        model_provider=agent.model_provider,
        model_name=agent.model_name,
        default_model_id=agent.default_model_id,
        selected_model_id=selected or agent.default_model_id,
        supports_kb_scope=agent_supports_kb_scope(agent.config if isinstance(agent.config, dict) else {}),
    )
