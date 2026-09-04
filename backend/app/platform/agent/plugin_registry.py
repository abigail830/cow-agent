"""Registry of agent runtime plugins."""

from __future__ import annotations

from app.agent_specific.proposal.plugin import ProposalPlugin
from app.agent_specific.slide.plugin import SlidePlugin
from app.agent_specific.viz.plugin import VIZ_TOOL_NAMES, VizCapabilityPlugin
from app.agent_specific.yl_worker2.plugin import YlWorker2Plugin
from app.platform.runtime.plugin import AgentPlugin
from app.shared.artifacts.plugin import ArtifactRuntimePlugin, DiagramArtifactPlugin, SandboxArtifactPlugin

_ALL_PLUGINS: tuple[AgentPlugin, ...] = (
    ProposalPlugin(),
    ArtifactRuntimePlugin(),
    DiagramArtifactPlugin(),
    SandboxArtifactPlugin(),
    SlidePlugin(),
    YlWorker2Plugin(),
)

_VIZ_CAPABILITY = VizCapabilityPlugin()


def iter_plugins_for_slug(agent_slug: str | None):
    for plugin in _ALL_PLUGINS:
        if plugin.matches(agent_slug):
            yield plugin


def tool_names_for_slug(agent_slug: str | None) -> frozenset[str]:
    names: set[str] = set()
    for plugin in iter_plugins_for_slug(agent_slug):
        names.update(plugin.tool_names)
    return frozenset(names)


def viz_tool_names() -> frozenset[str]:
    return VIZ_TOOL_NAMES


async def run_plugin_start(ctx) -> None:
    for plugin in iter_plugins_for_slug(ctx.agent_slug):
        await plugin.on_run_start(ctx)


async def run_plugin_end(ctx) -> None:
    for plugin in _ALL_PLUGINS:
        await plugin.on_run_end(ctx)


async def run_plugin_finalize_success(ctx, *, accumulator=None) -> None:
    for plugin in iter_plugins_for_slug(ctx.agent_slug):
        await plugin.on_finalize_success(ctx, accumulator=accumulator)


async def run_plugin_finalize_failure(ctx, *, accumulator=None) -> None:
    for plugin in iter_plugins_for_slug(ctx.agent_slug):
        await plugin.on_finalize_failure(ctx, accumulator=accumulator)
