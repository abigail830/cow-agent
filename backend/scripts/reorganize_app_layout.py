#!/usr/bin/env python3
"""One-shot layout migration for backend/app (already applied 2026-09-04).

Do not re-run unless restoring from an old branch. Kept for reference only.
"""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"

MOVES: list[tuple[str, str]] = [
    ("proposal", "agent_specific/proposal"),
    ("diagram", "agent_specific/diagram"),
    ("slide", "agent_specific/slide"),
    ("viz", "agent_specific/viz"),
    ("yl_worker2", "agent_specific/yl_worker2"),
    ("mdm", "agent_specific/mdm"),
    ("artifacts", "shared/artifacts"),
    ("sandbox", "shared/sandbox"),
    ("platform/agent_factory.py", "platform/agent/agent_factory.py"),
    ("platform/agent_bundle.py", "platform/agent/agent_bundle.py"),
    ("platform/profile_loader.py", "platform/agent/profile_loader.py"),
    ("platform/platform_sync.py", "platform/agent/platform_sync.py"),
    ("platform/skill_registry.py", "platform/agent/skill_registry.py"),
    ("platform/tool_registry.py", "platform/agent/tool_registry.py"),
    ("platform/allowed_tools.py", "platform/agent/allowed_tools.py"),
    ("platform/platform_instructions.py", "platform/agent/platform_instructions.py"),
    ("platform/mcp_registry.py", "platform/mcp/mcp_registry.py"),
    ("platform/mcp_config.py", "platform/mcp/mcp_config.py"),
    ("platform/mcp_connect.py", "platform/mcp/mcp_connect.py"),
    ("platform/mcp_compat.py", "platform/mcp/mcp_compat.py"),
    ("platform/hook_catalog.py", "platform/hooks/hook_catalog.py"),
    ("platform/hook_registry.py", "platform/hooks/hook_registry.py"),
    ("platform/hook_config.py", "platform/hooks/hook_config.py"),
    ("platform/hook_context.py", "platform/hooks/hook_context.py"),
    ("platform/model_registry.py", "platform/llm/model_registry.py"),
    ("platform/anthropic_client.py", "platform/llm/anthropic_client.py"),
    ("platform/utility_models.py", "platform/llm/utility_models.py"),
    ("platform/session_store.py", "platform/session/session_store.py"),
    ("platform/user_message_input.py", "platform/session/user_message_input.py"),
    ("platform/attachment_adapters.py", "platform/attachments/attachment_adapters.py"),
    ("platform/attachment_storage.py", "platform/attachments/attachment_storage.py"),
    ("platform/attachment_limits.py", "platform/attachments/attachment_limits.py"),
    ("platform/auth_sessions.py", "platform/auth/auth_sessions.py"),
    ("platform/current_user.py", "platform/auth/current_user.py"),
    ("platform/passwords.py", "platform/auth/passwords.py"),
    ("platform/secret_store.py", "platform/auth/secret_store.py"),
    ("middleware", "platform/hooks"),
    ("memory", "platform/memory"),
    ("guardrails", "platform/guardrails"),
    ("tools", "platform/agent"),
]

IMPORT_REPLACEMENTS: list[tuple[str, str]] = [
    ("app.proposal", "app.agent_specific.proposal"),
    ("app.diagram", "app.agent_specific.diagram"),
    ("app.slide", "app.agent_specific.slide"),
    ("app.viz", "app.agent_specific.viz"),
    ("app.yl_worker2", "app.agent_specific.yl_worker2"),
    ("app.mdm", "app.agent_specific.proposal.mdm"),
    ("app.artifacts", "app.shared.artifacts"),
    ("app.sandbox", "app.shared.sandbox"),
    ("app.platform.agent_factory", "app.platform.agent.agent_factory"),
    ("app.platform.agent_bundle", "app.platform.agent.agent_bundle"),
    ("app.platform.profile_loader", "app.platform.agent.profile_loader"),
    ("app.platform.platform_sync", "app.platform.agent.platform_sync"),
    ("app.platform.skill_registry", "app.platform.agent.skill_registry"),
    ("app.platform.tool_registry", "app.platform.agent.tool_registry"),
    ("app.platform.allowed_tools", "app.platform.agent.allowed_tools"),
    ("app.platform.platform_instructions", "app.platform.agent.platform_instructions"),
    ("app.platform.mcp_registry", "app.platform.mcp.mcp_registry"),
    ("app.platform.mcp_config", "app.platform.mcp.mcp_config"),
    ("app.platform.mcp_connect", "app.platform.mcp.mcp_connect"),
    ("app.platform.mcp_compat", "app.platform.mcp.mcp_compat"),
    ("app.platform.hook_catalog", "app.platform.hooks.hook_catalog"),
    ("app.platform.hook_registry", "app.platform.hooks.hook_registry"),
    ("app.platform.hook_config", "app.platform.hooks.hook_config"),
    ("app.platform.hook_context", "app.platform.hooks.hook_context"),
    ("app.platform.model_registry", "app.platform.llm.model_registry"),
    ("app.platform.anthropic_client", "app.platform.llm.anthropic_client"),
    ("app.platform.utility_models", "app.platform.llm.utility_models"),
    ("app.platform.session_store", "app.platform.session.session_store"),
    ("app.platform.user_message_input", "app.platform.session.user_message_input"),
    ("app.platform.attachment_adapters", "app.platform.attachments.attachment_adapters"),
    ("app.platform.attachment_storage", "app.platform.attachments.attachment_storage"),
    ("app.platform.attachment_limits", "app.platform.attachments.attachment_limits"),
    ("app.platform.auth_sessions", "app.platform.auth.auth_sessions"),
    ("app.platform.current_user", "app.platform.auth.current_user"),
    ("app.platform.passwords", "app.platform.auth.passwords"),
    ("app.platform.secret_store", "app.platform.auth.secret_store"),
    ("app.memory", "app.platform.memory"),
    ("app.guardrails", "app.platform.guardrails"),
    ("app.middleware.", "app.platform.hooks."),
]

if __name__ == "__main__":
    raise SystemExit("Already applied. See docstring; edit script only for reference.")
