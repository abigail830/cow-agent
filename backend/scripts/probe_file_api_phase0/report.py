"""Structured probe result types."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ProbeStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class ProbeResult:
    id: str
    label: str
    status: ProbeStatus
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["status"] = self.status.value
        return payload


@dataclass
class ProbeReport:
    started_at: str
    results: list[ProbeResult] = field(default_factory=list)

    def add(self, result: ProbeResult) -> None:
        self.results.append(result)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == ProbeStatus.PASS)

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == ProbeStatus.FAIL)

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == ProbeStatus.SKIP)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "summary": {
                "pass": self.passed,
                "fail": self.failed,
                "skip": self.skipped,
                "total": len(self.results),
            },
            "results": [r.to_dict() for r in self.results],
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


def new_report() -> ProbeReport:
    return ProbeReport(started_at=datetime.now(UTC).isoformat())
