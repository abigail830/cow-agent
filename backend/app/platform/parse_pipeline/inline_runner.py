from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]


def _parse_pipeline_cli_base() -> list[str]:
    cli = shutil.which("parse-pipeline")
    if cli:
        return [cli]
    return [sys.executable, "-m", "parse_pipeline.cli"]


async def run_inline_job(job_payload: dict) -> None:
    """Run parse-pipeline CLI in a subprocess (dev / no GHA)."""

    def _run() -> None:
        with tempfile.TemporaryDirectory(prefix="parse-job-") as tmp:
            job_file = Path(tmp) / "job.json"
            job_file.write_text(json.dumps(job_payload, ensure_ascii=False), encoding="utf-8")
            cmd = [*_parse_pipeline_cli_base(), "run-job", "--job-file", str(job_file), "--caller-id", "platform-inline"]
            logger.info("inline parse job: %s", job_payload.get("job_id"))
            env = os.environ.copy()
            env["PYTHONPATH"] = str(_REPO_ROOT / "parse-pipeline")
            result = subprocess.run(
                cmd,
                cwd=str(_REPO_ROOT / "parse-pipeline"),
                capture_output=True,
                text=True,
                env=env,
            )
            if result.returncode != 0:
                logger.error("inline parse failed: %s", result.stderr or result.stdout)
                raise RuntimeError(result.stderr or result.stdout or "parse job failed")

    await asyncio.to_thread(_run)


def schedule_inline_job(job_payload: dict) -> None:
    asyncio.create_task(_run_inline_safe(job_payload))


async def _run_inline_safe(job_payload: dict) -> None:
    job_id = job_payload.get("job_id")
    try:
        await run_inline_job(job_payload)
        await _finalize_inline_job(job_payload)
    except Exception:
        logger.exception("inline parse job failed job_id=%s", job_id)
        await _mark_inline_failed(job_payload)


async def _finalize_inline_job(job_payload: dict) -> None:
    import uuid

    from app.db.session import get_async_session_factory
    from app.platform.docstore.blob import parsed_artifact_exists
    from app.platform.docstore.repository import DocstoreRepository
    from app.platform.parse_pipeline.events import publish_attachment_parse_updated
    from app.platform.parse_pipeline.repository import ParseJobRepository

    source = job_payload.get("source") or {}
    attachment_id = uuid.UUID(str(source["source_id"]))
    chat_id = uuid.UUID(str(source["tenant_id"]))
    job_id = str(job_payload["job_id"])

    factory = get_async_session_factory()
    async with factory() as session:
        jobs = ParseJobRepository(session)
        await jobs.update_run_status(job_id, "succeeded")
        docstore = DocstoreRepository(session)
        if parsed_artifact_exists(chat_id, attachment_id, "meta_json"):
            row = await docstore.apply_parse_webhook(
                attachment_id,
                status="ready",
                stage_snapshot={
                    "current_stage": "finalize",
                    "message": "Parse complete",
                    "stages": [],
                },
            )
        else:
            row = await docstore.apply_parse_webhook(
                attachment_id,
                status="failed",
                stage_snapshot=None,
                error_code="ARTIFACT_MISSING",
                error_message="Parse finished but meta.json was not written",
            )
        await session.commit()
        if row is not None:
            from app.platform.parse_pipeline.serialization import attachment_out_extras

            publish_attachment_parse_updated(str(row.chat_id), {"attachment_id": str(row.id), **attachment_out_extras(row)})


async def _mark_inline_failed(job_payload: dict) -> None:
    import uuid

    from app.db.session import get_async_session_factory
    from app.platform.docstore.repository import DocstoreRepository
    from app.platform.parse_pipeline.events import publish_attachment_parse_updated
    from app.platform.parse_pipeline.repository import ParseJobRepository

    source = job_payload.get("source") or {}
    attachment_id = uuid.UUID(str(source["source_id"]))
    job_id = str(job_payload.get("job_id") or "")

    factory = get_async_session_factory()
    async with factory() as session:
        if job_id:
            await ParseJobRepository(session).update_run_status(job_id, "failed")
        row = await DocstoreRepository(session).apply_parse_webhook(
            attachment_id,
            status="failed",
            stage_snapshot=None,
            error_code="PARSE_FAILED",
            error_message="Inline parse job failed",
        )
        await session.commit()
        if row is not None:
            from app.platform.parse_pipeline.serialization import attachment_out_extras

            publish_attachment_parse_updated(str(row.chat_id), {"attachment_id": str(row.id), **attachment_out_extras(row)})
