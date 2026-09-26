from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from urllib.parse import unquote, urlparse

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[4]
_PARSE_PIPELINE_DIR = _REPO_ROOT / "parse-pipeline"


def _file_path_from_url(url: str) -> Path | None:
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return None
    return Path(unquote(parsed.path))


def _parse_pipeline_cli_base() -> list[str]:
    venv_cli = _PARSE_PIPELINE_DIR / ".venv" / "bin" / "parse-pipeline"
    if venv_cli.is_file():
        return [str(venv_cli)]
    cli = shutil.which("parse-pipeline")
    if cli:
        return [cli]
    venv_python = _PARSE_PIPELINE_DIR / ".venv" / "bin" / "python"
    if venv_python.is_file():
        return [str(venv_python), "-m", "parse_pipeline.cli"]
    return [sys.executable, "-m", "parse_pipeline.cli"]


def _parse_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(_PARSE_PIPELINE_DIR)
    venv_bin = _PARSE_PIPELINE_DIR / ".venv" / "bin"
    if venv_bin.is_dir():
        env["PATH"] = f"{venv_bin}{os.pathsep}{env.get('PATH', '')}"
    return env


def _ensure_original_on_disk(job_payload: dict) -> None:
    """Materialize blob-stored originals to the file:// path inline jobs expect."""

    from app.platform.attachments.storage import inline_attachment_path, load_inline_attachment

    storage = job_payload.get("storage") or {}
    read = storage.get("read") or {}
    read_url = str(read.get("url") or "")
    path = _file_path_from_url(read_url)
    if path is None:
        return
    if path.is_file():
        return

    source = job_payload.get("source") or {}
    chat_id = uuid.UUID(str(source["tenant_id"]))
    attachment_id = uuid.UUID(str(source["source_id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(load_inline_attachment(chat_id, attachment_id))
    logger.info(
        "materialized original for inline parse attachment_id=%s -> %s",
        attachment_id,
        path,
    )


def _ensure_parsed_write_dirs(job_payload: dict) -> None:
    storage = job_payload.get("storage") or {}
    write_specs = storage.get("write") or {}
    for target in write_specs.values():
        if not isinstance(target, dict):
            continue
        path = _file_path_from_url(str(target.get("url") or ""))
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            (path.parent / "figures").mkdir(parents=True, exist_ok=True)


async def run_inline_job(job_payload: dict) -> None:
    """Run parse-pipeline CLI in a subprocess (dev / no GHA)."""

    def _run() -> None:
        _ensure_original_on_disk(job_payload)
        _ensure_parsed_write_dirs(job_payload)
        with tempfile.TemporaryDirectory(prefix="parse-job-") as tmp:
            job_file = Path(tmp) / "job.json"
            job_file.write_text(json.dumps(job_payload, ensure_ascii=False), encoding="utf-8")
            cmd = [*_parse_pipeline_cli_base(), "run-job", "--job-file", str(job_file), "--caller-id", "platform-inline"]
            logger.info("inline parse job: %s", job_payload.get("job_id"))
            result = subprocess.run(
                cmd,
                cwd=str(_PARSE_PIPELINE_DIR),
                capture_output=True,
                text=True,
                env=_parse_subprocess_env(),
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


async def _sync_inline_artifacts_to_docstore(
    session,
    *,
    chat_id: uuid.UUID,
    attachment_id: uuid.UUID,
    job_payload: dict,
) -> None:
    from app.platform.docstore.blob import save_parsed_artifact, save_parsed_figure
    from app.platform.docstore.content_types import parsed_artifact_media_type
    from app.platform.docstore.repository import DocstoreRepository

    write_specs = (job_payload.get("storage") or {}).get("write") or {}
    docstore = DocstoreRepository(session)

    for artifact_key in ("content_md", "meta_json", "pageindex_json"):
        target = write_specs.get(artifact_key)
        if not isinstance(target, dict):
            continue
        path = _file_path_from_url(str(target.get("url") or ""))
        if path is None or not path.is_file():
            continue
        data = path.read_bytes()
        content_type = str(target.get("content_type") or parsed_artifact_media_type(artifact_key))
        save_parsed_artifact(
            chat_id,
            attachment_id,
            artifact_key,
            data,
            content_type=content_type,
        )
        await docstore.record_parsed_artifact(
            attachment_id,
            chat_id=chat_id,
            artifact_key=artifact_key,
            size_bytes=len(data),
            content_type=content_type,
        )

    content_target = write_specs.get("content_md")
    if not isinstance(content_target, dict):
        return
    content_path = _file_path_from_url(str(content_target.get("url") or ""))
    if content_path is None:
        return
    figures_dir = content_path.parent / "figures"
    if not figures_dir.is_dir():
        return
    for fig_path in sorted(figures_dir.iterdir()):
        if not fig_path.is_file():
            continue
        figure_id = fig_path.stem
        extension = fig_path.suffix.lstrip(".")
        if not figure_id or not extension:
            continue
        mime = f"image/{'jpeg' if extension == 'jpg' else extension}"
        save_parsed_figure(
            chat_id,
            attachment_id,
            figure_id,
            extension,
            fig_path.read_bytes(),
            content_type=mime,
        )


async def _finalize_inline_job(job_payload: dict) -> None:
    from app.db.models import ChatAttachment
    from app.db.session import get_async_session_factory
    from app.platform.docstore.manifest import parsed_artifact_in_manifest
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
        await _sync_inline_artifacts_to_docstore(
            session,
            chat_id=chat_id,
            attachment_id=attachment_id,
            job_payload=job_payload,
        )
        docstore = DocstoreRepository(session)
        attachment = await session.get(ChatAttachment, attachment_id)
        if attachment is not None and parsed_artifact_in_manifest(
            attachment.parsed_artifact_manifest,
            "meta_json",
        ):
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
            from app.platform.docstore.models import ParseStatus
            from app.platform.parse_pipeline.serialization import attachment_out_extras

            publish_attachment_parse_updated(str(row.chat_id), {"attachment_id": str(row.id), **attachment_out_extras(row)})
            if str(row.parse_status or "") == ParseStatus.READY.value:
                from app.platform.attachments.gist import schedule_attachment_gist

                schedule_attachment_gist(row.id)


async def _mark_inline_failed(job_payload: dict) -> None:
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
