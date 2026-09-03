from enum import Enum

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient

from app.config import Settings, get_settings
from app.platform.model_registry import _azure_responses_base_url


class UtilityPurpose(str, Enum):
    CHAT_TITLE = "chat_title"
    HISTORY_COMPACTION = "history_compaction"


class UtilityModelRegistry:
    """Platform utility LLM — isolated from user agent sessions."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def get_client(self, purpose: UtilityPurpose | None = None) -> OpenAIChatClient:
        s = self._settings
        return OpenAIChatClient(
            model=s.utility_deployment(),
            api_key=s.utility_api_key(),
            base_url=_azure_responses_base_url(s.utility_base_url()),
            api_version=s.utility_api_version(),
        )

    def _instructions_for(self, purpose: UtilityPurpose) -> str:
        if purpose == UtilityPurpose.CHAT_TITLE:
            return (
                "Generate a concise chat title (max 8 words) in the same language as the user. "
                "Reply with the title only, no quotes."
            )
        return (
            "Summarize the conversation history concisely. Preserve key facts, decisions, and tool outcomes. "
            "Omit reasoning traces. Reply with summary text only."
        )

    async def complete(
        self,
        purpose: UtilityPurpose,
        *,
        prompt: str,
        max_tokens: int = 256,
    ) -> str:
        client = self.get_client(purpose)
        agent = Agent(
            client=client,
            name=f"utility-{purpose.value}",
            instructions=self._instructions_for(purpose),
        )
        result = await agent.run(prompt)
        return (result.text or "").strip()

    async def smoke_test(self) -> str:
        return await self.complete(
            UtilityPurpose.CHAT_TITLE,
            prompt="User: What is 2+2?\nAssistant: 4",
        )
