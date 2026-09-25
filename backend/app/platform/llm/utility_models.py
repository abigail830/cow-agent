from enum import Enum

from agent_framework import Agent
from agent_framework.openai import OpenAIChatClient, OpenAIChatCompletionClient

from app.config import Settings, get_settings
from app.platform.llm.model_registry import _azure_responses_base_url, _openai_compatible_base_url


class UtilityPurpose(str, Enum):
    CHAT_TITLE = "chat_title"
    HISTORY_COMPACTION = "history_compaction"


def _uses_azure_responses_api(base_url: str) -> bool:
    normalized = base_url.rstrip("/").lower()
    return "cognitiveservices.azure.com" in normalized or ".openai.azure.com" in normalized


class UtilityModelRegistry:
    """Platform utility LLM — isolated from user agent sessions."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def get_client(
        self,
        purpose: UtilityPurpose | None = None,
    ) -> OpenAIChatClient | OpenAIChatCompletionClient:
        del purpose
        s = self._settings
        base_url = s.utility_base_url()
        if _uses_azure_responses_api(base_url):
            return OpenAIChatClient(
                model=s.utility_deployment(),
                api_key=s.utility_api_key(),
                base_url=_azure_responses_base_url(base_url),
                api_version=s.utility_api_version(),
            )
        return OpenAIChatCompletionClient(
            model=s.utility_deployment(),
            api_key=s.utility_api_key(),
            base_url=_openai_compatible_base_url(base_url),
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
            default_options={"max_tokens": max_tokens},
        )
        result = await agent.run(prompt)
        return (result.text or "").strip()

    async def smoke_test(self) -> str:
        return await self.complete(
            UtilityPurpose.CHAT_TITLE,
            prompt="User: What is 2+2?\nAssistant: 4",
            max_tokens=64,
        )
