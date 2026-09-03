"""Background Slidev build jobs — avoid blocking HTTP until build completes."""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from app.artifacts.spec import ArtifactSpec
from app.slide.artifact_builder import build_slide_artifact_spec
from app.slide.build_executor import run_slidev_build
from app.sandbox.types import SlidevBuildOutput

logger = logging.getLogger(__name__)

JobStatus = Literal["pending", "running", "done", "error"]


@dataclass
class SlideBuildJob:
    job_id: str
    chat_id: uuid.UUID
    slides_md: str
    title: str
    status: JobStatus = "pending"
    result: SlidevBuildOutput | None = None
    artifact_spec: ArtifactSpec | None = None
    error: str | None = None
    emitted: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)


_lock = threading.Lock()
_jobs: dict[str, SlideBuildJob] = {}
_chat_job_ids: dict[str, list[str]] = {}


def submit_slide_build_job(*, chat_id: uuid.UUID, slides_md: str, title: str) -> str:
    job_id = f"slide-job-{uuid.uuid4().hex[:12]}"
    job = SlideBuildJob(
        job_id=job_id,
        chat_id=chat_id,
        slides_md=slides_md,
        title=title,
    )
    with _lock:
        _jobs[job_id] = job
        _chat_job_ids.setdefault(str(chat_id), []).append(job_id)

    thread = threading.Thread(
        target=_run_job,
        args=(job_id,),
        name=f"slide-build-{job_id}",
        daemon=True,
    )
    thread.start()
    return job_id


def get_slide_build_job(job_id: str) -> SlideBuildJob | None:
    with _lock:
        return _jobs.get(job_id)


def drain_completed_slide_build_jobs(chat_id: uuid.UUID) -> list[ArtifactSpec]:
    """Return artifact specs for completed jobs not yet emitted for this chat."""
    chat_key = str(chat_id)
    specs: list[ArtifactSpec] = []
    with _lock:
        job_ids = list(_chat_job_ids.get(chat_key, []))
        for job_id in job_ids:
            job = _jobs.get(job_id)
            if job is None or job.emitted:
                continue
            with job._lock:
                if job.status not in ("done", "error"):
                    continue
                job.emitted = True
                if job.status == "done" and job.artifact_spec is not None:
                    specs.append(job.artifact_spec)
        _chat_job_ids[chat_key] = [
            jid for jid in job_ids if _jobs.get(jid) is not None and not _jobs[jid].emitted
        ]
    return specs


def has_pending_slide_build_jobs(chat_id: uuid.UUID) -> bool:
    chat_key = str(chat_id)
    with _lock:
        for job_id in _chat_job_ids.get(chat_key, []):
            job = _jobs.get(job_id)
            if job is None or job.emitted:
                continue
            with job._lock:
                if job.status in ("pending", "running"):
                    return True
    return False


def reset_slide_build_jobs(chat_id: uuid.UUID | None = None) -> None:
    with _lock:
        if chat_id is None:
            _jobs.clear()
            _chat_job_ids.clear()
            return
        chat_key = str(chat_id)
        for job_id in _chat_job_ids.pop(chat_key, []):
            _jobs.pop(job_id, None)


def wait_for_slide_build_jobs(chat_id: uuid.UUID, *, timeout_seconds: float) -> None:
    deadline = time.monotonic() + max(1.0, timeout_seconds)
    while time.monotonic() < deadline and has_pending_slide_build_jobs(chat_id):
        time.sleep(0.25)


def _run_job(job_id: str) -> None:
    job = get_slide_build_job(job_id)
    if job is None:
        return

    with job._lock:
        job.status = "running"

    build = run_slidev_build(job.slides_md)
    with job._lock:
        job.result = build
        if build.error:
            job.status = "error"
            job.error = build.error
            return

        try:
            job.artifact_spec = build_slide_artifact_spec(
                title=job.title,
                source=job.slides_md,
                chat_id=job.chat_id,
                dist_files=build.dist_files,
                pdf_bytes=build.pdf_bytes,
            )
            job.status = "done"
        except (OSError, RuntimeError) as exc:
            job.status = "error"
            job.error = str(exc).strip() or "Failed to persist slide artifact."
            logger.exception("Slide build job %s persistence failed", job_id)
