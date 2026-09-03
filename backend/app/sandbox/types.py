from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SlidevBuildOutput:
    dist_files: dict[str, bytes] = field(default_factory=dict)
    pdf_bytes: bytes | None = None
    logs: str = ""
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.dist_files)
