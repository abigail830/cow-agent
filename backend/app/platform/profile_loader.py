import copy
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from pydantic import AliasChoices

from app.config import Settings, get_settings
from app.platform.model_registry import ModelProvider

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
AGENTS_ROOT = _BACKEND_ROOT / "agents"
_AGENT_MCP_FILENAME = "mcp_servers.yaml"
_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def mcp_storage_name(slug: str, local_name: str) -> str:
    """Globally unique DB key; local_name is the tool name exposed to the model."""
    return f"{slug}:{local_name}"


def mcp_tool_name(storage_name: str, connection: dict[str, Any] | None = None) -> str:
    if connection and connection.get("tool_name"):
        return str(connection["tool_name"])
    if ":" in storage_name:
        return storage_name.split(":", 1)[1]
    return storage_name


@dataclass
class AgentProfile:
    slug: str
    name: str
    description: str | None
    model_provider: str
    model_name: str
    instructions: str
    skill_paths: list[Path]
    mcp_servers: list[str]
    mcp_server_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    extra_config: dict[str, Any] = field(default_factory=dict)


def _env_aliases_for_field(field_info: Any) -> list[str]:
    alias = field_info.validation_alias
    if alias is None:
        return []
    if isinstance(alias, str):
        return [alias]
    if isinstance(alias, AliasChoices):
        return [str(choice) for choice in alias.choices]
    return [str(alias)]


def _settings_value_for_env_key(key: str) -> str | None:
    settings = get_settings()
    for field_name, field_info in Settings.model_fields.items():
        for alias in _env_aliases_for_field(field_info):
            if alias != key:
                continue
            value = getattr(settings, field_name, None)
            if value is not None and str(value).strip():
                return str(value)
    attr = key.lower()
    if hasattr(settings, attr):
        value = getattr(settings, attr, None)
        if value is not None and str(value).strip():
            return str(value)
    return None


def _resolve_env(value: str) -> str:
    def repl(match: re.Match[str]) -> str:
        expr = match.group(1)
        default: str | None = None
        if ":-" in expr:
            key, default = expr.split(":-", 1)
            key = key.strip()
            default = default.strip()
        else:
            key = expr.strip()
        env_val = os.environ.get(key)
        if env_val:
            return env_val
        settings_val = _settings_value_for_env_key(key)
        if settings_val:
            return settings_val
        if default is not None:
            return default
        return match.group(0)

    if not isinstance(value, str):
        return value
    return _ENV_PATTERN.sub(repl, value)


def _resolve_env_deep(obj: Any) -> Any:
    if isinstance(obj, str):
        return _resolve_env(obj)
    if isinstance(obj, list):
        return [_resolve_env_deep(v) for v in obj]
    if isinstance(obj, dict):
        return {k: _resolve_env_deep(v) for k, v in obj.items()}
    return obj


def _deep_merge_mcp(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge_mcp(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _parse_profile_mcp_servers(raw: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    """Parse profile mcp_servers as a list of keys or a per-server override map."""
    raw_mcp = raw.get("mcp_servers")
    if isinstance(raw_mcp, dict):
        return list(raw_mcp.keys()), _resolve_env_deep(raw_mcp)
    if isinstance(raw_mcp, list):
        names = [str(name) for name in raw_mcp]
        raw_env = raw.get("mcp_env") or {}
        overrides = _resolve_env_deep(raw_env) if isinstance(raw_env, dict) else {}
        return names, overrides
    return [], {}


def load_agent_mcp_servers(
    agent_dir: Path,
    overrides: dict[str, dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Load MCP servers from mcp_servers.yaml and merge profile-level overrides."""
    path = agent_dir / _AGENT_MCP_FILENAME
    servers: dict[str, Any] = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        servers = dict(raw.get("servers") or {})

    for name, override in (overrides or {}).items():
        if name in servers:
            servers[name] = _deep_merge_mcp(servers[name], override)
        else:
            servers[name] = copy.deepcopy(override)

    return {name: _resolve_env_deep(cfg) for name, cfg in servers.items()}


def _discover_skill_paths(
    agent_dir: Path,
    skills_dir_name: str,
    *,
    enabled_skills: list[str] | None = None,
) -> list[Path]:
    skills_root = agent_dir / skills_dir_name
    if not skills_root.is_dir():
        return []
    allowed = {name.strip() for name in (enabled_skills or []) if str(name).strip()}
    paths: list[Path] = []
    for child in sorted(skills_root.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            if allowed and child.name not in allowed:
                continue
            paths.append(child)
    return paths


def load_agent_profile(agent_dir: Path) -> AgentProfile:
    profile_path = agent_dir / "profile.yaml"
    if not profile_path.exists():
        raise ValueError(f"Missing profile.yaml in {agent_dir}")

    raw = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    slug = str(raw.get("id") or agent_dir.name).strip()
    if not slug:
        raise ValueError(f"Agent profile in {agent_dir} requires id")
    if slug != agent_dir.name:
        raise ValueError(
            f"Agent profile id '{slug}' must match directory name '{agent_dir.name}' ({profile_path})"
        )

    prompt_file = raw.get("prompt_file") or "system_prompt.md"
    prompt_path = agent_dir / prompt_file
    if not prompt_path.exists():
        raise ValueError(f"Prompt file not found: {prompt_path}")
    instructions = prompt_path.read_text(encoding="utf-8").strip()

    model_provider = raw.get("model_provider")
    if not model_provider:
        model_val = _resolve_env(str(raw.get("model") or ""))
        if "claude" in model_val.lower():
            model_provider = ModelProvider.AZURE_ANTHROPIC.value
        else:
            model_provider = ModelProvider.AZURE_OPENAI.value
    model_name = _resolve_env(str(raw.get("model") or ""))
    if not model_name:
        settings = get_settings()
        if model_provider == ModelProvider.AZURE_ANTHROPIC.value:
            model_name = settings.claude_azure_foundry_model or "claude-sonnet-4-6"
        else:
            model_name = settings.azure_openai_deployment

    skills_dir = raw.get("skills_dir") or "skills"
    enabled_skills = raw.get("skills")
    if enabled_skills is not None and not isinstance(enabled_skills, list):
        enabled_skills = None
    skill_paths = _discover_skill_paths(
        agent_dir,
        skills_dir,
        enabled_skills=[str(name) for name in enabled_skills] if enabled_skills else None,
    )

    mcp_servers, mcp_server_overrides = _parse_profile_mcp_servers(raw)

    reserved = {
        "id",
        "name",
        "description",
        "version",
        "model",
        "model_provider",
        "prompt_file",
        "skills_dir",
        "skills",
        "mcp_servers",
        "mcp_env",
        "invocation_modes",
        "delegates",
    }
    extra_config = {k: v for k, v in raw.items() if k not in reserved}

    return AgentProfile(
        slug=slug,
        name=str(raw.get("name") or slug),
        description=raw.get("description"),
        model_provider=str(model_provider),
        model_name=model_name,
        instructions=instructions,
        skill_paths=skill_paths,
        mcp_servers=mcp_servers,
        mcp_server_overrides=mcp_server_overrides,
        extra_config=extra_config,
    )


def discover_agent_profiles() -> list[AgentProfile]:
    if not AGENTS_ROOT.is_dir():
        return []
    profiles: list[AgentProfile] = []
    for child in sorted(AGENTS_ROOT.iterdir()):
        if child.is_dir() and (child / "profile.yaml").exists():
            profiles.append(load_agent_profile(child))
    return profiles
