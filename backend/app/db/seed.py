from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.platform_sync import sync_platform_config


async def ensure_dev_seed(session: AsyncSession) -> None:
    """Load agents/MCP/skills from YAML profiles and platform config."""
    await sync_platform_config(session)
