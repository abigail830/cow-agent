from __future__ import annotations

from typing import Protocol

from app.shared.sandbox.types import SlidevBuildOutput


class SandboxProvider(Protocol):
    name: str

    def build_slidev(
        self,
        *,
        slides_md: str,
        exports: list[str] | None = None,
        timeout_seconds: float | None = None,
    ) -> SlidevBuildOutput: ...
