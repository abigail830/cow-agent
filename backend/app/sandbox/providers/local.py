"""Local sandbox — stores source only; no Slidev build (dev fallback)."""

from __future__ import annotations

from app.sandbox.types import SlidevBuildOutput


class LocalSandboxProvider:
    name = "local"

    def build_slidev(
        self,
        *,
        slides_md: str,
        exports: list[str] | None = None,
        timeout_seconds: float | None = None,
    ) -> SlidevBuildOutput:
        _ = exports, timeout_seconds
        return SlidevBuildOutput(
            dist_files={},
            pdf_bytes=None,
            logs="Local sandbox: skipped Slidev build; only slides.md will be stored.",
        )
