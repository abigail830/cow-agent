from unittest.mock import MagicMock, patch

from app.platform.model_registry import ModelProvider, ModelProviderRegistry


def test_anthropic_client_enables_detailed_tool_errors():
    registry = ModelProviderRegistry()
    with patch("app.platform.model_registry.PlatformAnthropicClient") as mock_cls:
        registry.create_azure_anthropic_client()
        _, kwargs = mock_cls.call_args
        assert kwargs["function_invocation_configuration"] == {"include_detailed_errors": True}


def test_openai_client_enables_detailed_tool_errors():
    registry = ModelProviderRegistry()
    with patch("app.platform.model_registry.OpenAIChatClient") as mock_cls:
        registry.create_azure_openai_client()
        _, kwargs = mock_cls.call_args
        assert kwargs["function_invocation_configuration"] == {"include_detailed_errors": True}


def test_create_agent_uses_configured_client():
    registry = ModelProviderRegistry()
    mock_client = MagicMock()
    with patch.object(registry, "create_azure_anthropic_client", return_value=mock_client):
        agent = registry.create_agent(
            name="test",
            instructions="test",
            model_provider=ModelProvider.AZURE_ANTHROPIC,
        )
    assert agent.client is mock_client
