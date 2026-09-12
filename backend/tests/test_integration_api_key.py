from app.platform.integrations.providers.hybrid_search import HybridSearchIntegrationProvider
from app.platform.integrations.registry import integration_auth_kind
from app.platform.integrations.token_service import _secret_to_tokens, _tokens_to_secret
from app.platform.integrations.types import OAuthTokenBundle


def test_hybrid_search_provider_is_api_key():
    provider = HybridSearchIntegrationProvider()
    assert provider.auth_kind == "api_key"
    assert provider.id == "hybrid-search"
    assert integration_auth_kind("hybrid-search") == "api_key"


def test_zhipu_web_search_provider_is_api_key():
    from app.platform.integrations.providers.zhipu_web_search import ZhipuWebSearchIntegrationProvider

    provider = ZhipuWebSearchIntegrationProvider()
    assert provider.auth_kind == "api_key"
    assert provider.id == "zhipu-web-search"
    assert integration_auth_kind("zhipu-web-search") == "api_key"


def test_hybrid_search_mask_api_key_label():
    assert HybridSearchIntegrationProvider.mask_api_key_label("abcd") == "••••"
    assert HybridSearchIntegrationProvider.mask_api_key_label("sk-live-12345678") == "••••5678"


def test_api_key_secret_roundtrip():
    bundle = OAuthTokenBundle(
        access_token="user-secret-key",
        refresh_token=None,
        expires_at_ms=4_102_444_800_000,
        scopes=[],
        account_label="••••ckey",
        metadata={"auth_kind": "api_key"},
    )
    stored = _secret_to_tokens(_tokens_to_secret(bundle))
    assert stored is not None
    assert stored.access_token == "user-secret-key"
    assert stored.refresh_token is None
