import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import MemoryAppendIn, MemoryOut, MemoryRemoveIn, MemoryReplaceIn
from app.db.session import get_db
from app.memory.long_term.formatter import parse_bullets, validate_line
from app.memory.long_term.repository import MemoryRepository, MemoryScope
from app.platform.current_user import get_current_user, get_current_user_id

router = APIRouter(prefix="/memories", tags=["memories"])


async def _commit_and_out(db: AsyncSession, snapshot) -> MemoryOut:
    """Commit then refresh ORM attrs — avoid lazy IO on expired objects (MissingGreenlet)."""
    await db.commit()
    await db.refresh(snapshot)
    return _to_out(snapshot)


def _to_out(snapshot) -> MemoryOut:
    bullets = []
    for prefix, text in parse_bullets(snapshot.content):
        bullets.append(
            {
                "prefix": prefix,
                "text": text,
                "line": f"[!] {text}" if prefix == "[!]" else f"- {text}",
                "kind": "constraint" if prefix == "[!]" else "bullet",
            }
        )
    return MemoryOut(
        scope=snapshot.scope,
        agent_id=snapshot.agent_id,
        content=snapshot.content,
        revision=snapshot.revision,
        bullets=bullets,
        updated_at=snapshot.updated_at.isoformat() if snapshot.updated_at else None,
    )


@router.get("/user", response_model=MemoryOut)
async def get_user_memory(
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MemoryOut:
    repo = MemoryRepository(db)
    snapshot = await repo.get_or_create_snapshot(user_id, MemoryScope("user"))
    return await _commit_and_out(db, snapshot)


@router.get("/agents/{agent_id}", response_model=MemoryOut)
async def get_agent_memory(
    agent_id: uuid.UUID,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MemoryOut:
    repo = MemoryRepository(db)
    snapshot = await repo.get_or_create_snapshot(user_id, MemoryScope("agent", agent_id=agent_id))
    return await _commit_and_out(db, snapshot)


@router.put("/user", response_model=MemoryOut)
async def replace_user_memory(
    body: MemoryReplaceIn,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MemoryOut:
    repo = MemoryRepository(db)
    snapshot = await repo.replace_content(user_id, MemoryScope("user"), body.content, source="ui")
    return await _commit_and_out(db, snapshot)


@router.put("/agents/{agent_id}", response_model=MemoryOut)
async def replace_agent_memory(
    agent_id: uuid.UUID,
    body: MemoryReplaceIn,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MemoryOut:
    repo = MemoryRepository(db)
    snapshot = await repo.replace_content(
        user_id,
        MemoryScope("agent", agent_id=agent_id),
        body.content,
        source="ui",
    )
    return await _commit_and_out(db, snapshot)


@router.post("/append", response_model=MemoryOut)
async def append_memory(
    body: MemoryAppendIn,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MemoryOut:
    if body.scope == "agent" and body.agent_id is None:
        raise HTTPException(status_code=400, detail="agent_id required for agent scope")
    if body.scope == "user" and body.agent_id is not None:
        raise HTTPException(status_code=400, detail="agent_id must be null for user scope")

    lines = []
    for raw in body.lines:
        if body.is_constraint or raw.strip().startswith("[!]"):
            text = raw.strip().removeprefix("[!]").strip()
            lines.append(validate_line(f"[!] {text}"))
        else:
            lines.append(validate_line(raw))

    memory_scope = MemoryScope(
        body.scope,
        agent_id=body.agent_id if body.scope == "agent" else None,
    )
    repo = MemoryRepository(db)
    snapshot, _ = await repo.append_lines(user_id, memory_scope, lines, source=body.source)
    return await _commit_and_out(db, snapshot)


@router.post("/remove", response_model=MemoryOut)
async def remove_memory(
    body: MemoryRemoveIn,
    user_id: uuid.UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> MemoryOut:
    if body.scope == "agent" and body.agent_id is None:
        raise HTTPException(status_code=400, detail="agent_id required for agent scope")

    repo = MemoryRepository(db)
    if body.scope == "agent":
        memory_scope = MemoryScope("agent", agent_id=body.agent_id)
        await repo.remove_lines(
            user_id,
            memory_scope,
            match=body.match,
            also_search_user_scope=body.also_search_user,
        )
        snapshot = await repo.get_or_create_snapshot(user_id, memory_scope)
    else:
        memory_scope = MemoryScope("user")
        await repo.remove_lines(user_id, memory_scope, match=body.match)
        snapshot = await repo.get_or_create_snapshot(user_id, memory_scope)

    return await _commit_and_out(db, snapshot)
