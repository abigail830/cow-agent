from enum import Enum

from agent_framework import Agent
from app.platform.llm.anthropic_client import FILES_API_BETA, PlatformAnthropicClient
from agent_framework.openai import OpenAIChatClient, OpenAIChatCompletionClient

from app.config import Settings, get_settings


def _azure_responses_base_url(base_url: str) -> str:
    """Build Azure OpenAI Responses API base URL (.../openai/v1/)."""
    url = base_url.rstrip("/")
    if url.endswith("/openai/v1"):
        return f"{url}/"
    if url.endswith("/openai"):
        return f"{url}/v1/"
    return url if url.endswith("/") else f"{url}/"


def _openai_compatible_base_url(base_url: str) -> str:
    """Normalize OpenAI-compatible base URL (SiliconFlow, DeepSeek, etc.)."""
    url = base_url.rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return f"{url}/"


class ModelProvider(str, Enum):
    AZURE_OPENAI = "azure_openai"
    AZURE_ANTHROPIC = "azure_anthropic"
    SILICONFLOW = "siliconflow"
    DASHSCOPE = "dashscope"
    DEEPSEEK = "deepseek"


_FUNCTION_INVOCATION_CONFIG = {
    "include_detailed_errors": True,
}


class ModelProviderRegistry:
    """Build MAF chat clients and agents from platform / agent configuration."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def create_azure_openai_client(
        self,
        *,
        deployment: str | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        api_version: str | None = None,
    ) -> OpenAIChatClient:
        s = self._settings
        resolved_base = base_url or s.azure_openai_base_url
        return OpenAIChatClient(
            model=deployment or s.azure_openai_deployment,
            api_key=api_key or s.azure_api_key,
            base_url=_azure_responses_base_url(resolved_base),
            api_version=api_version or s.azure_openai_api_version,
            function_invocation_configuration=_FUNCTION_INVOCATION_CONFIG,
        )

    def create_azure_anthropic_client(self, *, model: str | None = None) -> PlatformAnthropicClient:
        s = self._settings
        if not s.claude_azure_api_key or not s.claude_azure_foundry_endpoint:
            raise ValueError("Claude is not configured (CLAUDE_AZURE_* env vars)")
        return PlatformAnthropicClient(
            api_key=s.claude_azure_api_key,
            model=model or s.claude_azure_foundry_model,
            base_url=s.claude_azure_foundry_endpoint.rstrip("/"),
            additional_beta_flags=[FILES_API_BETA],
            function_invocation_configuration=_FUNCTION_INVOCATION_CONFIG,
        )

    def create_siliconflow_client(self, *, model: str | None = None) -> OpenAIChatCompletionClient:
        """SiliconFlow uses standard OpenAI Chat Completions, not Azure Responses API."""
        return self._create_openai_compatible_client(
            api_key=self._settings.siliconflow_api_key,
            base_url=self._settings.siliconflow_base_url,
            model=model or self._settings.siliconflow_default_model,
            provider_label="SiliconFlow",
            api_key_env="SILICONFLOW_API_KEY",
        )

    def create_dashscope_client(self, *, model: str | None = None) -> OpenAIChatCompletionClient:
        """Alibaba DashScope compatible-mode Chat Completions API."""
        return self._create_openai_compatible_client(
            api_key=self._settings.dashscope_api_key,
            base_url=self._settings.dashscope_base_url,
            model=model or self._settings.dashscope_default_model,
            provider_label="DashScope",
            api_key_env="DASHSCOPE_API_KEY",
        )

    def create_deepseek_client(self, *, model: str | None = None) -> OpenAIChatCompletionClient:
        """DeepSeek OpenAI-compatible Chat Completions API."""
        return self._create_openai_compatible_client(
            api_key=self._settings.deepseek_api_key,
            base_url=self._settings.deepseek_base_url,
            model=model or self._settings.deepseek_default_model,
            provider_label="DeepSeek",
            api_key_env="DEEPSEEK_API_KEY",
        )

    def _create_openai_compatible_client(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str | None,
        provider_label: str,
        api_key_env: str,
    ) -> OpenAIChatCompletionClient:
        if not api_key:
            raise ValueError(f"{provider_label} is not configured ({api_key_env} env var)")
        if not model:
            raise ValueError(
                f"{provider_label} model is required — set model in profile.yaml or catalog deployment"
            )
        return OpenAIChatCompletionClient(
            model=model,
            api_key=api_key,
            base_url=_openai_compatible_base_url(base_url),
            function_invocation_configuration=_FUNCTION_INVOCATION_CONFIG,
        )

    def create_agent(
        self,
        *,
        name: str,
        instructions: str,
        model_provider: ModelProvider = ModelProvider.AZURE_OPENAI,
        model_name: str | None = None,
        context_providers: list | None = None,
        middleware: list | None = None,
        tools: list | None = None,
        compaction_strategy: object | None = None,
        require_per_service_call_history_persistence: bool = False,
    ) -> Agent:
        if model_provider == ModelProvider.AZURE_OPENAI:
            client = self.create_azure_openai_client(deployment=model_name)
        elif model_provider == ModelProvider.AZURE_ANTHROPIC:
            client = self.create_azure_anthropic_client(model=model_name)
        elif model_provider == ModelProvider.SILICONFLOW:
            client = self.create_siliconflow_client(model=model_name)
        elif model_provider == ModelProvider.DASHSCOPE:
            client = self.create_dashscope_client(model=model_name)
        elif model_provider == ModelProvider.DEEPSEEK:
            client = self.create_deepseek_client(model=model_name)
        else:
            raise NotImplementedError(f"Provider {model_provider} not implemented")

        default_options: dict | None = None
        if model_provider == ModelProvider.AZURE_ANTHROPIC:
            default_options = {"max_tokens": 16000}
            if self._settings.claude_enable_thinking:
                default_options["thinking"] = {"type": "enabled", "budget_tokens": 1024}

        return Agent(
            client=client,
            name=name,
            instructions=instructions,
            context_providers=context_providers,
            middleware=middleware,
            tools=tools,
            default_options=default_options,
            compaction_strategy=compaction_strategy,
            require_per_service_call_history_persistence=require_per_service_call_history_persistence,
        )

    async def smoke_test_claude(self, prompt: str = "Reply with exactly: OK") -> str:
        agent = self.create_agent(
            name="smoke-claude",
            instructions="You are a test assistant. Be extremely brief.",
            model_provider=ModelProvider.AZURE_ANTHROPIC,
        )
        result = await agent.run(prompt)
        return result.text or ""

    async def smoke_test_primary(self, prompt: str = "Reply with exactly: OK") -> str:
        agent = self.create_agent(
            name="smoke-primary",
            instructions="You are a test assistant. Be extremely brief.",
        )
        result = await agent.run(prompt)
        return result.text or ""
