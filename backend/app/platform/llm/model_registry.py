from enum import Enum

from agent_framework import Agent
from app.platform.llm.openai_compatible_client import OpenAICompatibleReasoningClient
from agent_framework.openai import OpenAIChatCompletionClient

from app.config import Settings, get_settings


def _openai_compatible_base_url(base_url: str) -> str:
    """Normalize OpenAI-compatible base URL (SiliconFlow, DeepSeek, etc.)."""
    url = base_url.rstrip("/")
    if not url.endswith("/v1"):
        url = f"{url}/v1"
    return f"{url}/"


class ModelProvider(str, Enum):
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

    def create_siliconflow_client(self, *, model: str | None = None) -> OpenAIChatCompletionClient:
        """SiliconFlow uses standard OpenAI Chat Completions, not Azure Responses API."""
        return self._create_openai_compatible_client(
            api_key=self._settings.siliconflow_api_key,
            base_url=self._settings.siliconflow_base_url,
            model=model or self._settings.siliconflow_default_model,
            provider_label="SiliconFlow",
            api_key_env="SILICONFLOW_API_KEY",
        )

    def create_dashscope_client(self, *, model: str | None = None) -> OpenAICompatibleReasoningClient:
        """Alibaba DashScope compatible-mode Chat Completions (Qwen thinking + tool calls)."""
        return self._create_openai_compatible_client(
            api_key=self._settings.dashscope_api_key,
            base_url=self._settings.dashscope_base_url,
            model=model or self._settings.dashscope_default_model,
            provider_label="DashScope",
            api_key_env="DASHSCOPE_API_KEY",
            client_cls=OpenAICompatibleReasoningClient,
        )

    def create_deepseek_client(self, *, model: str | None = None) -> OpenAICompatibleReasoningClient:
        """DeepSeek OpenAI-compatible Chat Completions (thinking-mode aware)."""
        return self._create_openai_compatible_client(
            api_key=self._settings.deepseek_api_key,
            base_url=self._settings.deepseek_base_url,
            model=model or self._settings.deepseek_default_model,
            provider_label="DeepSeek",
            api_key_env="DEEPSEEK_API_KEY",
            client_cls=OpenAICompatibleReasoningClient,
        )

    def _create_openai_compatible_client(
        self,
        *,
        api_key: str | None,
        base_url: str,
        model: str | None,
        provider_label: str,
        api_key_env: str,
        client_cls: type[OpenAIChatCompletionClient] | None = None,
    ) -> OpenAIChatCompletionClient:
        if not api_key:
            raise ValueError(f"{provider_label} is not configured ({api_key_env} env var)")
        if not model:
            raise ValueError(
                f"{provider_label} model is required — set model in profile.yaml or catalog deployment"
            )
        cls = client_cls or OpenAIChatCompletionClient
        return cls(
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
        model_provider: ModelProvider = ModelProvider.DASHSCOPE,
        model_name: str | None = None,
        context_providers: list | None = None,
        middleware: list | None = None,
        tools: list | None = None,
        compaction_strategy: object | None = None,
        default_options: dict | None = None,
        require_per_service_call_history_persistence: bool = False,
    ) -> Agent:
        if model_provider == ModelProvider.SILICONFLOW:
            client = self.create_siliconflow_client(model=model_name)
        elif model_provider == ModelProvider.DASHSCOPE:
            client = self.create_dashscope_client(model=model_name)
        elif model_provider == ModelProvider.DEEPSEEK:
            client = self.create_deepseek_client(model=model_name)
        else:
            raise NotImplementedError(f"Provider {model_provider} not implemented")

        merged_default_options: dict | None = dict(default_options) if default_options else None

        return Agent(
            client=client,
            name=name,
            instructions=instructions,
            context_providers=context_providers,
            middleware=middleware,
            tools=tools,
            default_options=merged_default_options,
            compaction_strategy=compaction_strategy,
            require_per_service_call_history_persistence=require_per_service_call_history_persistence,
        )

    async def smoke_test_dashscope(self, prompt: str = "Reply with exactly: OK") -> str:
        s = self._settings
        model = s.dashscope_default_model or s.utility_deployment() or "qwen3.7-plus"
        agent = self.create_agent(
            name="smoke-dashscope",
            instructions="You are a test assistant. Be extremely brief.",
            model_provider=ModelProvider.DASHSCOPE,
            model_name=model,
        )
        result = await agent.run(prompt)
        return result.text or ""
