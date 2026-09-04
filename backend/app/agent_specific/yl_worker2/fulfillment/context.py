"""Per-run fulfillment forms context (session draft before Confirm API)."""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunFulfillmentFormsState:
    chat_id: uuid.UUID | None = None
    forms: list[dict[str, Any]] = field(default_factory=list)
    dirty: bool = False

    def mark_dirty(self) -> None:
        self.dirty = True


_run_fulfillment_forms_state: ContextVar[RunFulfillmentFormsState | None] = ContextVar(
    "run_fulfillment_forms_state",
    default=None,
)


def init_run_fulfillment_forms_state(
    *,
    chat_id: uuid.UUID | None = None,
    initial_forms: list[dict[str, Any]] | None = None,
) -> RunFulfillmentFormsState:
    ctx = RunFulfillmentFormsState(
        chat_id=chat_id,
        forms=list(initial_forms or []),
    )
    _run_fulfillment_forms_state.set(ctx)
    return ctx


def get_run_fulfillment_forms_state() -> RunFulfillmentFormsState | None:
    return _run_fulfillment_forms_state.get()


def reset_run_fulfillment_forms_state() -> None:
    _run_fulfillment_forms_state.set(None)
