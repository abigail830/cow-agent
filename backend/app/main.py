import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.db.redis_client import check_redis_connection
from sqlalchemy import func, select

from app.db.models import AgentModel
from app.db.seed import ensure_dev_seed
from app.db.session import check_db_connection, get_async_session_factory, init_db_engine
from app.platform.profile_loader import discover_agent_profiles
from app.platform.model_registry import ModelProviderRegistry
from app.platform.utility_models import UtilityModelRegistry

logger = logging.getLogger(__name__)
IS_VERCEL = os.getenv("VERCEL") == "1"


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_db_engine()
    try:
        await check_db_connection()
        logger.info("Database connection OK")
    except Exception:
        logger.exception("Database connection failed")
        if not IS_VERCEL:
            raise
    try:
        await check_redis_connection()
        logger.info("Redis connection OK")
    except Exception:
        logger.warning("Redis connection failed — session cache will use DB only")
    try:
        factory = get_async_session_factory()
        disk_profiles = discover_agent_profiles()
        should_sync = settings.sync_agent_profiles_on_startup and not IS_VERCEL
        async with factory() as session:
            if should_sync:
                logger.info("Syncing agent profiles from disk (%d profiles)...", len(disk_profiles))
                await ensure_dev_seed(session)
            else:
                if IS_VERCEL:
                    logger.info("Skipping agent profile sync on Vercel (read agents from database)")
                else:
                    logger.info(
                        "Skipping agent profile sync (SYNC_AGENT_PROFILES_ON_STARTUP=false); "
                        "run scripts/sync_agent_profiles.py after profile changes"
                    )
                from app.platform.platform_sync import ensure_platform_user

                await ensure_platform_user(session)
                await session.commit()
            synced = (
                await session.execute(
                    select(func.count()).select_from(AgentModel).where(AgentModel.slug.isnot(None))
                )
            ).scalar_one()
        logger.info(
            "Agent profiles: %d on disk (%s) -> %d in database%s",
            len(disk_profiles),
            ", ".join(p.slug for p in disk_profiles) or "none",
            synced,
            " (synced)" if should_sync else "",
        )
        logger.info(
            "Models: primary=%s utility=%s",
            settings.azure_openai_deployment,
            settings.utility_deployment(),
        )
    except Exception:
        logger.exception("Startup seed/profile sync failed")
        if not IS_VERCEL:
            raise
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        db_ok = await check_db_connection()
        try:
            redis_ok = await check_redis_connection()
        except Exception:
            redis_ok = False
        return {
            "status": "ok" if db_ok else "degraded",
            "database": db_ok,
            "redis": redis_ok,
            "primary_deployment": settings.azure_openai_deployment,
            "utility_deployment": settings.utility_deployment(),
        }

    app.include_router(api_router)

    @app.get("/health/models")
    async def health_models():
        """Smoke test primary + utility models (may incur API cost)."""
        registry = ModelProviderRegistry()
        primary = await registry.smoke_test_primary()
        utility = await UtilityModelRegistry().smoke_test()
        payload = {
            "primary": {"deployment": settings.azure_openai_deployment, "response": primary[:200]},
            "utility": {"deployment": settings.utility_deployment(), "response": utility[:200]},
        }
        if settings.claude_azure_api_key:
            try:
                claude = await registry.smoke_test_claude()
                payload["claude"] = {
                    "model": settings.claude_azure_foundry_model,
                    "response": claude[:200],
                }
            except Exception as exc:
                payload["claude"] = {"error": str(exc)}
        return payload

    return app


app = create_app()
