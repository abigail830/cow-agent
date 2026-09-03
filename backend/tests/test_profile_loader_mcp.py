"""Profile-level MCP env merge and ${ENV} resolution."""

import os
from pathlib import Path

import yaml

from app.platform.profile_loader import (
    _parse_profile_mcp_servers,
    _resolve_env,
    load_agent_mcp_servers,
    load_agent_profile,
)


def test_load_agent_mcp_servers_merges_profile_env(tmp_path: Path, monkeypatch):
    agent_dir = tmp_path / "demo-agent"
    agent_dir.mkdir()
    (agent_dir / "mcp_servers.yaml").write_text(
        yaml.dump(
            {
                "servers": {
                    "postgres": {
                        "command": "npx",
                        "args": ["-y", "mcp-postgres@latest"],
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("DEMO_POSTGRES_URL", "postgresql://demo/db")

    overrides = {
        "postgres": {
            "env": {
                "DATABASE_URL": "${DEMO_POSTGRES_URL}",
                "DB_READ_ONLY": "true",
            }
        }
    }
    configs = load_agent_mcp_servers(agent_dir, overrides)

    assert configs["postgres"]["command"] == "npx"
    assert configs["postgres"]["env"]["DATABASE_URL"] == "postgresql://demo/db"
    assert configs["postgres"]["env"]["DB_READ_ONLY"] == "true"


def test_parse_profile_mcp_servers_dict_format():
    raw = {
        "mcp_servers": {
            "mysql": {
                "env": {
                    "MYSQL_HOST": "${OTHER_AGENT_MYSQL_HOST}",
                }
            }
        }
    }
    names, overrides = _parse_profile_mcp_servers(raw)
    assert names == ["mysql"]
    assert overrides["mysql"]["env"]["MYSQL_HOST"] == "${OTHER_AGENT_MYSQL_HOST}"


def test_parse_profile_mcp_servers_list_with_mcp_env():
    raw = {
        "mcp_servers": ["postgres"],
        "mcp_env": {
            "postgres": {
                "env": {"DATABASE_URL": "${PG_URL}"},
            }
        },
    }
    names, overrides = _parse_profile_mcp_servers(raw)
    assert names == ["postgres"]
    assert overrides["postgres"]["env"]["DATABASE_URL"] == "${PG_URL}"


def test_load_agent_profile_parses_mcp_dict(tmp_path: Path):
    agent_dir = tmp_path / "demo-agent"
    agent_dir.mkdir()
    (agent_dir / "profile.yaml").write_text(
        yaml.dump(
            {
                "id": "demo-agent",
                "name": "Demo",
                "model_provider": "azure_anthropic",
                "model": "claude-test",
                "mcp_servers": {
                    "postgres": {
                        "env": {"DATABASE_URL": "${DEMO_URL}"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (agent_dir / "system_prompt.md").write_text("You are a demo agent.", encoding="utf-8")

    profile = load_agent_profile(agent_dir)

    assert profile.mcp_servers == ["postgres"]
    assert profile.mcp_server_overrides["postgres"]["env"]["DATABASE_URL"] == "${DEMO_URL}"


def test_resolve_env_prefers_os_environ(monkeypatch):
    monkeypatch.setenv("MY_CUSTOM_DB", "mysql://from-env")
    assert _resolve_env("${MY_CUSTOM_DB}") == "mysql://from-env"


def test_resolve_env_falls_back_to_settings_validation_alias(monkeypatch):
    monkeypatch.delenv("CLAUDE_AZURE_FOUNDRY_MODEL", raising=False)
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("CLAUDE_AZURE_FOUNDRY_MODEL", "claude-from-settings")
    get_settings.cache_clear()

    assert _resolve_env("${CLAUDE_AZURE_FOUNDRY_MODEL}") == "claude-from-settings"
    get_settings.cache_clear()
