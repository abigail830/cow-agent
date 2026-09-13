"""Tests for platform model catalog."""

from pathlib import Path

import yaml

from app.platform.llm.model_catalog import ModelCatalog, ModelEntry, reload_model_catalog


def test_model_catalog_loads_entries(monkeypatch, tmp_path: Path):
    catalog_path = tmp_path / "models.yaml"
    catalog_path.write_text(
        yaml.dump(
            {
                "providers": {"azure_openai": {"base_url": "https://example.openai.azure.com/openai"}},
                "models": [
                    {
                        "id": "gpt-test",
                        "label": "GPT Test",
                        "provider": "azure_openai",
                        "deployment": "gpt-test-deployment",
                        "enabled": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.platform.llm.model_catalog._CATALOG_PATH", catalog_path)
    catalog = reload_model_catalog()
    entry = catalog.get("gpt-test")
    assert entry is not None
    assert entry.deployment == "gpt-test-deployment"
    assert catalog.find_by_provider_deployment("azure_openai", "gpt-test-deployment") == entry


def test_model_roles_default_to_chat(monkeypatch, tmp_path: Path):
    catalog_path = tmp_path / "models.yaml"
    catalog_path.write_text(
        yaml.dump(
            {
                "providers": {"dashscope": {"base_url": "https://dashscope.example/v1"}},
                "models": [
                    {
                        "id": "legacy-chat",
                        "label": "Legacy",
                        "provider": "dashscope",
                        "deployment": "legacy-chat",
                        "enabled": True,
                    },
                    {
                        "id": "qwen-vl-max",
                        "label": "Qwen VL",
                        "provider": "dashscope",
                        "deployment": "qwen-vl-max",
                        "enabled": True,
                        "roles": ["vision_worker"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.platform.llm.model_catalog._CATALOG_PATH", catalog_path)
    catalog = reload_model_catalog()
    legacy = catalog.get("legacy-chat")
    vision = catalog.get("qwen-vl-max")
    assert legacy is not None and legacy.has_role("chat")
    assert vision is not None and vision.has_role("vision_worker")
    assert not vision.has_role("chat")


def test_list_for_role_excludes_other_roles(monkeypatch, tmp_path: Path):
    catalog_path = tmp_path / "models.yaml"
    catalog_path.write_text(
        yaml.dump(
            {
                "providers": {"dashscope": {"base_url": "https://dashscope.example/v1"}},
                "models": [
                    {
                        "id": "chat-model",
                        "label": "Chat",
                        "provider": "dashscope",
                        "deployment": "chat-model",
                        "enabled": True,
                        "roles": ["chat"],
                    },
                    {
                        "id": "vision-model",
                        "label": "Vision",
                        "provider": "dashscope",
                        "deployment": "vision-model",
                        "enabled": True,
                        "roles": ["vision_worker"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DASHSCOPE_API_KEY", "test-key")
    monkeypatch.setattr("app.platform.llm.model_catalog._CATALOG_PATH", catalog_path)
    catalog = reload_model_catalog()
    from app.config import get_settings

    settings = get_settings()
    chat_ids = {entry.id for entry in catalog.list_for_role("chat", settings)}
    vision_ids = {entry.id for entry in catalog.list_for_role("vision_worker", settings)}
    assert chat_ids == {"chat-model"}
    assert vision_ids == {"vision-model"}


def test_resolve_default_model_id_prefers_explicit_default():
    catalog = ModelCatalog(
        models={
            "claude-sonnet-4-6": ModelEntry(
                id="claude-sonnet-4-6",
                label="Claude",
                provider="azure_anthropic",
                deployment="claude-sonnet-4-6",
            )
        },
        providers={},
    )
    resolved = catalog.resolve_default_model_id(
        default_model="claude-sonnet-4-6",
        model_provider="azure_anthropic",
        model_name="other-name",
    )
    assert resolved == "claude-sonnet-4-6"
