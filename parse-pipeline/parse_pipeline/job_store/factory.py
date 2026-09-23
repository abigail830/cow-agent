from __future__ import annotations

from parse_pipeline.config import Settings, get_settings
from parse_pipeline.job_store.base import JobStore
from parse_pipeline.job_store.memory import MemoryJobStore

_store: JobStore | None = None


def get_job_store(settings: Settings | None = None) -> JobStore:
    global _store
    if _store is not None:
        return _store
    settings = settings or get_settings()
    if settings.job_store in {"memory", "none"}:
        _store = MemoryJobStore()
        return _store
    if settings.job_store == "postgres":
        raise NotImplementedError("JOB_STORE=postgres is not implemented yet; use memory")
    raise ValueError(f"unknown JOB_STORE: {settings.job_store}")


def reset_job_store() -> None:
    global _store
    _store = None
