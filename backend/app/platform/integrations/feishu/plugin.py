"""Initialize Feishu user token context for content-studio runs."""

from __future__ import annotations

from app.config import get_settings
from app.platform.integrations.feishu.context import init_feishu_context, reset_feishu_context
from app.platform.integrations.feishu.tools import FEISHU_TOOL_NAMES
from app.platform.integrations.providers.feishu import FEISHU_PROVIDER_ID
from app.platform.integrations.token_service import IntegrationTokenService
from app.platform.runtime.plugin import AgentPlugin, RunContext


class FeishuPlugin(AgentPlugin):
    slug = "content-studio"
    tool_names = FEISHU_TOOL_NAMES

    async def on_run_start(self, ctx: RunContext) -> None:
        settings = get_settings()
        api_base = (settings.feishu_api_base or "https://open.feishu.cn").rstrip("/")
        token_service = IntegrationTokenService(ctx.db)
        stored = await token_service.load_tokens(
            user_id=ctx.chat.user_id,
            provider=FEISHU_PROVIDER_ID,
        )
        access_token = await token_service.get_valid_access_token(
            user_id=ctx.chat.user_id,
            provider=FEISHU_PROVIDER_ID,
        )
        init_feishu_context(
            access_token=access_token,
            account_label=stored.account_label if stored else None,
            api_base=api_base,
        )

    async def on_run_end(self, ctx: RunContext) -> None:
        reset_feishu_context()
