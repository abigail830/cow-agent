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
