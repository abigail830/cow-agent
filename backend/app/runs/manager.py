import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum


class RunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


FinalizeFn = Callable[[], Awaitable[None]]


@dataclass
class ActiveRun:
    run_id: uuid.UUID
    chat_id: uuid.UUID
    user_message_id: uuid.UUID
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    status: RunStatus = RunStatus.RUNNING
    finalize_fn: FinalizeFn | None = field(default=None, repr=False)
    finalized: bool = False


class RunManager:
    """In-process registry of active chat runs (one running run per chat)."""

    def __init__(self) -> None:
        self._runs: dict[uuid.UUID, ActiveRun] = {}
        self._chat_to_run: dict[uuid.UUID, uuid.UUID] = {}
        self._lock = asyncio.Lock()

    async def start_run(self, chat_id: uuid.UUID, user_message_id: uuid.UUID) -> ActiveRun:
        async with self._lock:
            existing_id = self._chat_to_run.get(chat_id)
            if existing_id is not None:
                existing = self._runs.get(existing_id)
                if existing is not None and existing.status == RunStatus.RUNNING:
                    existing.stop_event.set()
                    existing.status = RunStatus.CANCELLED

            run = ActiveRun(
                run_id=uuid.uuid4(),
                chat_id=chat_id,
                user_message_id=user_message_id,
            )
            self._runs[run.run_id] = run
            self._chat_to_run[chat_id] = run.run_id
            return run

    async def register_finalize(self, run_id: uuid.UUID, finalize_fn: FinalizeFn) -> None:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is not None:
                run.finalize_fn = finalize_fn

    async def get(self, run_id: uuid.UUID) -> ActiveRun | None:
        return self._runs.get(run_id)

    async def _run_finalize_once(self, run: ActiveRun) -> bool:
        async with self._lock:
            if run.finalized:
                return False
            run.finalized = True
            finalize_fn = run.finalize_fn
        if finalize_fn is not None:
            await finalize_fn()
        return True

    async def cancel(self, run_id: uuid.UUID) -> ActiveRun | None:
        async with self._lock:
            run = self._runs.get(run_id)
            if run is None or run.status != RunStatus.RUNNING:
                return run
            run.stop_event.set()
            run.status = RunStatus.CANCELLED
        await self._run_finalize_once(run)
        return run

    async def finalize_cancelled(self, run_id: uuid.UUID) -> bool:
        run = self._runs.get(run_id)
        if run is None:
            return False
        return await self._run_finalize_once(run)

    async def complete(self, run_id: uuid.UUID) -> None:
        async with self._lock:
            run = self._runs.pop(run_id, None)
            if run is None:
                return
            if run.status == RunStatus.RUNNING:
                run.status = RunStatus.COMPLETED
            self._chat_to_run.pop(run.chat_id, None)


_manager: RunManager | None = None


def get_run_manager() -> RunManager:
    global _manager
    if _manager is None:
        _manager = RunManager()
    return _manager
