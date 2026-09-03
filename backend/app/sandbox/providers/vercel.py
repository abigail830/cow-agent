"""Vercel Sandbox provider — not implemented; use E2B or local."""

from __future__ import annotations

from app.sandbox.types import SlidevBuildOutput


class VercelSandboxProvider:
    name = "vercel"

    def build_slidev(
        self,
        *,
        slides_md: str,
        exports: list[str] | None = None,
        timeout_seconds: float | None = None,
    ) -> SlidevBuildOutput:
        _ = slides_md, exports, timeout_seconds
        return SlidevBuildOutput(
            error=(
                "SANDBOX_PROVIDER=vercel is not implemented yet. "
                "Use SANDBOX_PROVIDER=e2b or local."
            ),
        )
