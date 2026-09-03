"""Block tool invocations not listed in profile allowed_tools."""

from __future__ import annotations

from agent_framework import FunctionInvocationContext, FunctionMiddleware


class AllowedToolsMiddleware(FunctionMiddleware):
    """Deny function calls whose name is outside the profile allowlist."""

    def __init__(self, allowed_names: set[str]) -> None:
        self._allowed = allowed_names

    async def process(self, context: FunctionInvocationContext, call_next) -> None:
        name = context.function.name
        if name in self._allowed:
            await call_next()
            return

        props = context.function.additional_properties or {}
        normalized = props.get("_mcp_normalized_name")
        remote = props.get("_mcp_remote_name")
        if isinstance(normalized, str) and normalized in self._allowed:
            await call_next()
            return
        if isinstance(remote, str) and remote in self._allowed:
            await call_next()
            return

        # Soft-fail: return an error payload to the model and let the agent loop continue.
        # Raising MiddlewareTermination would set should_terminate and stop the run before
        # the model can retry with an allowed tool (e.g. render_html_ppt).
        context.result = {
            "error": f"Tool not allowed: {name}",
            "hint": (
                "This tool is not listed in profile allowed_tools. "
                "Agents with skills_dir auto-allow load_skill and read_skill_resource. "
                "Pick another allowed tool and continue."
            ),
        }
