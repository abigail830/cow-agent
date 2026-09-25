import pytest

from app.config import Settings
from app.platform.integrations.providers.feishu import (
    FEISHU_PROVIDER_ID,
    FeishuIntegrationProvider,
    feishu_document_id_from_url,
)
from app.platform.integrations.registry import get_integration_provider, integration_auth_kind


def _feishu_settings(**overrides: object) -> Settings:
    base = {
        "azure_api_key": "k",
        "azure_openai_base_url": "https://example.com",
        "azure_openai_api_version": "2024-01-01",
        "azure_openai_deployment": "gpt",
        "database_url": "postgresql://example",
    }
    base.update(overrides)
    return Settings.model_construct(**base)


def test_feishu_provider_registered():
    provider = get_integration_provider(FEISHU_PROVIDER_ID)
    assert provider is not None
    assert integration_auth_kind(FEISHU_PROVIDER_ID) == "oauth"


def test_feishu_is_platform_configured():
    configured = FeishuIntegrationProvider(
        settings=_feishu_settings(
            feishu_app_id="cli_test",
            feishu_app_secret="secret",
            feishu_oauth_redirect_uri="http://127.0.0.1:8000/api/v1/integrations/feishu/callback",
        )
    )
    missing = FeishuIntegrationProvider(settings=_feishu_settings())
    assert configured.is_platform_configured() is True
    assert missing.is_platform_configured() is False


def test_feishu_build_authorize_url():
    provider = FeishuIntegrationProvider(
        settings=_feishu_settings(
            feishu_app_id="cli_test",
            feishu_app_secret="secret",
            feishu_oauth_redirect_uri="http://127.0.0.1:8000/callback",
        )
    )
    url = provider.build_authorize_url(state="state-123", code_challenge="unused")
    assert "accounts.feishu.cn/open-apis/authen/v1/authorize" in url
    assert "client_id=cli_test" in url
    assert "state=state-123" in url
    assert "im%3Amessage" in url or "im:message" in url


def test_feishu_document_id_from_url():
    doc_id = feishu_document_id_from_url("https://example.feishu.cn/docx/doxcnAbCdEf123456")
    assert doc_id == "doxcnAbCdEf123456"


@pytest.mark.asyncio
async def test_feishu_exchange_code(monkeypatch):
    provider = FeishuIntegrationProvider(
        settings=_feishu_settings(
            feishu_app_id="cli_test",
            feishu_app_secret="secret",
            feishu_oauth_redirect_uri="http://127.0.0.1:8000/callback",
        )
    )

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload
            self.content = b"{}"
            self.status_code = 200

        @property
        def is_success(self) -> bool:
            return True

        def json(self) -> dict:
            return self._payload

    responses = [
        FakeResponse(
            {
                "code": 0,
                "access_token": "u-token",
                "refresh_token": "u-refresh",
                "expires_in": 7200,
                "scope": "offline_access im:message:readonly",
            }
        ),
        FakeResponse(
            {
                "code": 0,
                "data": {"email": "user@example.com", "name": "User"},
            }
        ),
    ]

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url: str, json: dict, headers: dict):
            assert "oauth/token" in url
            assert json["grant_type"] == "authorization_code"
            return responses.pop(0)

        async def get(self, url: str, headers: dict):
            assert "user_info" in url
            return responses.pop(0)

    monkeypatch.setattr(
        "app.platform.integrations.providers.feishu.httpx.AsyncClient",
        lambda **kwargs: FakeClient(),
    )

    bundle = await provider.exchange_code(code="auth-code", code_verifier="ignored")
    assert bundle.access_token == "u-token"
    assert bundle.refresh_token == "u-refresh"
    assert bundle.account_label == "user@example.com"
