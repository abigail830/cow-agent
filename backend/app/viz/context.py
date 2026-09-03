"""Per-run context for SQL results and pending visualization events."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any

from app.viz.spec import VizResult, VizSpec


@dataclass
class SqlResultEntry:
    call_id: str
    tool_name: str
    rows: list[dict[str, Any]]
    columns: list[str]


@dataclass
class RunVizState:
    sql_results: dict[str, SqlResultEntry] = field(default_factory=dict)
    latest_call_id: str | None = None
    pending_specs: list[VizSpec] = field(default_factory=list)
    emitted_specs: list[VizSpec] = field(default_factory=list)

    def store_sql(
        self,
        *,
        call_id: str,
        tool_name: str,
        rows: list[dict[str, Any]],
        columns: list[str],
    ) -> None:
        entry = SqlResultEntry(call_id=call_id, tool_name=tool_name, rows=rows, columns=columns)
        self.sql_results[call_id] = entry
        self.latest_call_id = call_id

    def resolve_entry(self, source_call_id: str | None) -> SqlResultEntry | None:
        if source_call_id and source_call_id in self.sql_results:
            return self.sql_results[source_call_id]
        if self.latest_call_id:
            return self.sql_results.get(self.latest_call_id)
        if self.sql_results:
            return next(reversed(self.sql_results.values()))
        return None

    def queue_viz(self, result: VizResult, *, source_call_id: str | None = None) -> bool:
        """Queue a viz spec. Returns False when deduplicated or skipped."""
        if result.spec is None or result.status == "skipped":
            return False

        spec = result.spec
        if source_call_id and not spec.source_call_id:
            spec = spec.model_copy(update={"source_call_id": source_call_id})

        key = (spec.kind, spec.title, spec.source_call_id)
        for existing in (*self.pending_specs, *self.emitted_specs):
            if (existing.kind, existing.title, existing.source_call_id) == key:
                return False
        self.pending_specs.append(spec)
        return True

    def drain_pending(self) -> list[VizSpec]:
        batch = list(self.pending_specs)
        self.pending_specs.clear()
        self.emitted_specs.extend(batch)
        return batch


_run_viz_state: ContextVar[RunVizState | None] = ContextVar("run_viz_state", default=None)


def init_run_viz_state() -> RunVizState:
    state = RunVizState()
    _run_viz_state.set(state)
    return state


def get_run_viz_state() -> RunVizState | None:
    return _run_viz_state.get()


def reset_run_viz_state() -> None:
    _run_viz_state.set(None)


def new_call_id() -> str:
    return f"sql-{uuid.uuid4().hex[:12]}"
