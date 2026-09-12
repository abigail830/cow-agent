"""Profile resolves model deployment from catalog default_model."""

from pathlib import Path

import yaml

from app.platform.agent.profile_loader import AGENTS_ROOT, load_agent_profile


def test_profile_uses_catalog_deployment_when_model_omitted():
    profile = load_agent_profile(AGENTS_ROOT / "content-studio")
    assert profile.default_model_id == "claude-sonnet-4-6"
    assert profile.model_name == "claude-sonnet-4-6"
    assert profile.model_provider == "azure_anthropic"


def test_profile_catalog_deployment_for_dashscope_minimax(tmp_path: Path, monkeypatch):
    catalog_path = tmp_path / "models.yaml"
    catalog_path.write_text(
        yaml.dump(
            {
                "providers": {"dashscope": {"base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1"}},
                "models": [
                    {
                        "id": "minimax-m3",
                        "label": "MiniMax M3",
                        "provider": "dashscope",
                        "deployment": "MiniMax/MiniMax-M3",
                        "enabled": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("app.platform.llm.model_catalog._CATALOG_PATH", catalog_path)
    from app.platform.llm import model_catalog

    model_catalog.reload_model_catalog()

    agent_dir = tmp_path / "test-agent"
    agent_dir.mkdir()
    (agent_dir / "profile.yaml").write_text(
        yaml.dump(
            {
                "id": "test-agent",
                "name": "Test",
                "model_provider": "dashscope",
                "default_model": "minimax-m3",
                "prompt_file": "system_prompt.md",
            }
        ),
        encoding="utf-8",
    )
    (agent_dir / "system_prompt.md").write_text("You are a test agent.", encoding="utf-8")

    profile = load_agent_profile(agent_dir)
    assert profile.model_name == "MiniMax/MiniMax-M3"

    model_catalog.reload_model_catalog()
