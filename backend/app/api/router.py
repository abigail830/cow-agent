from fastapi import APIRouter

from app.api.routes import agents, auth, chats, config, memories, runs, users, yl_worker2_triggers

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(agents.router)
api_router.include_router(chats.router)
api_router.include_router(config.router)
api_router.include_router(memories.router)
api_router.include_router(runs.router)
api_router.include_router(yl_worker2_triggers.router)
