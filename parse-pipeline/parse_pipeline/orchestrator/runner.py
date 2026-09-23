from __future__ import annotations

import logging
import time
from typing import Any, Callable

from parse_pipeline.config import Settings, get_settings
from parse_pipeline.job_store.base import JobRecord
from parse_pipeline.job_store.factory import get_job_store
from parse_pipeline.normalize.artifacts import NormalizedArtifacts, artifacts_to_bytes, normalize_text_artifacts
from parse_pipeline.providers.local.sheet import extract_sheet_bytes
from parse_pipeline.providers.local.text import extract_text_bytes
from parse_pipeline.providers.document_mind.client import DEFAULT_OUTPUT_FORMATS
from parse_pipeline.schemas.job import JobArtifacts, JobError, JobProgress, JobStatus, PipelineId
from parse_pipeline.schemas.stages import StageId, StageStatus
from parse_pipeline.schemas.storage import StorageSpec
from parse_pipeline.storage.io import fetch_bytes, parse_storage_spec, write_artifact
from parse_pipeline.webhooks import sender

logger = logging.getLogger(__name__)


class JobRunner:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.store = get_job_store(self.settings)

    async def run_job(self, job_id: str) -> JobRecord | None:
        record = await self.store.get_job(job_id)
        if record is None:
            return None
        started = time.monotonic()
        try:
            record.status = JobStatus.RUNNING
            await self.store.save_job(record)
            await self._run_pipeline(record)
            record.status = JobStatus.SUCCEEDED
            record.stats = {"duration_ms": int((time.monotonic() - started) * 1000)}
            await self.store.save_job(record)
            await sender.emit_job_completed(record)
        except Exception as exc:
            logger.exception("job failed job_id=%s", job_id)
            record.status = JobStatus.FAILED
            record.error = JobError(
                code=getattr(exc, "code", "PARSE_FAILED"),
                message=str(exc),
                stage_id=record.current_stage,
            )
            record.stats = {"duration_ms": int((time.monotonic() - started) * 1000)}
            await self.store.save_job(record)
            await sender.emit_job_failed(record)
        return record

    async def _run_pipeline(self, record: JobRecord) -> None:
        spec = parse_storage_spec(record.storage_spec)
        filename = record.source.get("filename") or spec.read.filename or "document"
        pipeline_id = record.pipeline_id

        file_bytes = await self._stage_fetch(record, spec)
        await self._maybe_skip_analyze(record, pipeline_id)

        normalized = await self._parse_stages(record, pipeline_id, file_bytes, filename)
        normalized = await self._stage_normalize(record, normalized, pipeline_id)
        await self._stage_write(record, spec, normalized)
        await self._stage_finalize(record)

    async def _stage_fetch(self, record: JobRecord, spec: StorageSpec) -> bytes:
        await self._begin_stage(record, StageId.FETCH)
        data = await fetch_bytes(spec.read)
        await self._finish_stage(
            record,
            StageId.FETCH,
            outputs={"bytes_read": len(data)},
        )
        return data

    async def _maybe_skip_analyze(self, record: JobRecord, pipeline_id: str) -> None:
        reason = None
        if pipeline_id in {
            PipelineId.PDF_STANDARD.value,
            PipelineId.OFFICE_STANDARD.value,
            PipelineId.DOCUMENT_MIND_GENERIC.value,
        }:
            reason = "pdf_dm_only_v1"
        elif pipeline_id == PipelineId.TEXT_STANDARD.value:
            reason = "local_text_no_analyze"
        elif pipeline_id == PipelineId.SHEET_STANDARD.value:
            reason = "local_sheet_no_analyze"
        await self._skip_stage(record, StageId.ANALYZE, reason=reason)

    async def _parse_stages(
        self,
        record: JobRecord,
        pipeline_id: str,
        file_bytes: bytes,
        filename: str,
    ) -> NormalizedArtifacts:
        if pipeline_id == PipelineId.TEXT_STANDARD.value:
            return await self._parse_local_text(record, file_bytes)
        if pipeline_id == PipelineId.SHEET_STANDARD.value:
            return await self._parse_local_sheet(record, file_bytes, filename)
        if pipeline_id in {
            PipelineId.PDF_STANDARD.value,
            PipelineId.OFFICE_STANDARD.value,
            PipelineId.DOCUMENT_MIND_GENERIC.value,
        }:
            return await self._parse_document_mind(record, file_bytes, filename, pipeline_id)
        raise ValueError(f"unsupported pipeline_id: {pipeline_id}")

    async def _parse_local_text(self, record: JobRecord, file_bytes: bytes) -> NormalizedArtifacts:
        await self._skip_stage(record, StageId.PARSE_SUBMIT, reason="sync_local")
        await self._skip_stage(record, StageId.PARSE_WAIT, reason="sync_local")
        await self._begin_stage(record, StageId.PARSE_COLLECT)
        content, warnings = extract_text_bytes(file_bytes)
        await self._finish_stage(
            record,
            StageId.PARSE_COLLECT,
            outputs={"provider_id": "local_text", "line_count": content.count("\n") + 1},
        )
        record.provider_id = "local_text"
        return normalize_text_artifacts(
            content=content,
            job_id=record.job_id,
            pipeline_id=record.pipeline_id,
            parse_engine="local_text",
            provider_id="local_text",
            warnings=warnings,
        )

    async def _parse_local_sheet(
        self,
        record: JobRecord,
        file_bytes: bytes,
        filename: str,
    ) -> NormalizedArtifacts:
        max_rows = int((record.options or {}).get("table_max_rows_per_sheet") or 2000)
        await self._skip_stage(record, StageId.PARSE_SUBMIT, reason="sync_local")
        await self._skip_stage(record, StageId.PARSE_WAIT, reason="sync_local")
        await self._begin_stage(record, StageId.PARSE_COLLECT)
        try:
            content, warnings = extract_sheet_bytes(file_bytes, filename, max_rows)
            provider_id = "local_sheet"
        except Exception as exc:
            logger.warning("local sheet failed, falling back to document_mind: %s", exc)
            await self._finish_stage(
                record,
                StageId.PARSE_COLLECT,
                status=StageStatus.SKIPPED,
                outputs={"fallback": "document_mind", "error": str(exc)},
            )
            return await self._parse_document_mind(record, file_bytes, filename, record.pipeline_id)
        await self._finish_stage(
            record,
            StageId.PARSE_COLLECT,
            outputs={"provider_id": provider_id},
        )
        record.provider_id = provider_id
        return normalize_text_artifacts(
            content=content,
            job_id=record.job_id,
            pipeline_id=record.pipeline_id,
            parse_engine="local_sheet",
            provider_id=provider_id,
            warnings=warnings,
        )

    async def _parse_document_mind(
        self,
        record: JobRecord,
        file_bytes: bytes,
        filename: str,
        pipeline_id: str,
    ) -> NormalizedArtifacts:
        import asyncio

        from parse_pipeline.providers.document_mind.client import build_client_from_settings

        record.provider_id = "document_mind"
        if not self.settings.document_mind_configured:
            raise RuntimeError("Document Mind credentials not configured (DOCUMENT_MIND_ACCESS_KEY_ID/SECRET)")

        client = build_client_from_settings(self.settings, record.options)
        dm_opts = (record.options or {}).get("document_mind") or {}
        output_formats = list(dm_opts.get("output_formats") or DEFAULT_OUTPUT_FORMATS)
        poll_state: dict[str, Any] = {}

        await self._begin_stage(record, StageId.PARSE_SUBMIT)

        def _submit() -> str:
            return client.submit(file_bytes, filename, output_formats=output_formats)

        task_id = await asyncio.to_thread(_submit)
        await self._finish_stage(
            record,
            StageId.PARSE_SUBMIT,
            outputs={
                "provider_id": "document_mind",
                "external_job_id": task_id,
                "output_formats": output_formats,
            },
        )

        await self._begin_stage(record, StageId.PARSE_WAIT)

        async def _on_poll(status_data: dict[str, Any]) -> None:
            poll_state["external_status"] = status_data.get("Status") or status_data.get("status")
            pages = status_data.get("NumberOfSuccessfulParsing") or status_data.get("number_of_successful_parsing")
            if pages is not None:
                poll_state["pages_done"] = pages
            outputs = {
                "provider_id": "document_mind",
                "external_job_id": task_id,
                **poll_state,
            }
            message = f"Document Mind {outputs.get('external_status') or 'processing'}"
            if "pages_done" in outputs:
                message = f"{message} ({outputs['pages_done']} pages)"
            record.progress = JobProgress(message=message)
            await self.store.save_job(record)
            await self._update_stage_outputs(record, StageId.PARSE_WAIT, outputs=outputs)
            refreshed = await self.store.get_job(record.job_id)
            if refreshed is not None:
                record.stages = refreshed.stages
                record.progress = refreshed.progress or record.progress

        await client.poll_until_done(task_id, on_poll=_on_poll)
        wait_outputs = {"provider_id": "document_mind", "external_job_id": task_id, **poll_state}
        await self._finish_stage(record, StageId.PARSE_WAIT, outputs=wait_outputs)

        await self._begin_stage(record, StageId.PARSE_COLLECT)

        def _collect() -> tuple[str, dict[str, Any] | None]:
            layouts = client.collect_all_layouts(task_id)
            markdown = client.layouts_to_markdown(layouts)
            pageindex = {"layouts": layouts, "external_job_id": task_id} if layouts else None
            return markdown, pageindex

        markdown, pageindex = await asyncio.to_thread(_collect)
        await self._finish_stage(
            record,
            StageId.PARSE_COLLECT,
            outputs={
                "provider_id": "document_mind",
                "external_job_id": task_id,
                "layout_count": len(pageindex.get("layouts", [])) if pageindex else 0,
            },
        )
        return normalize_text_artifacts(
            content=markdown,
            job_id=record.job_id,
            pipeline_id=pipeline_id,
            parse_engine="document_mind",
            provider_id="document_mind",
            pageindex=pageindex,
        )

    async def _stage_normalize(
        self,
        record: JobRecord,
        normalized: NormalizedArtifacts,
        pipeline_id: str,
    ) -> NormalizedArtifacts:
        await self._begin_stage(record, StageId.NORMALIZE)
        await self._finish_stage(
            record,
            StageId.NORMALIZE,
            outputs={
                "line_count": normalized.meta_json.get("line_count"),
                "page_count": normalized.meta_json.get("page_count"),
            },
        )
        return normalized

    async def _stage_write(self, record: JobRecord, spec: StorageSpec, normalized: NormalizedArtifacts) -> None:
        await self._begin_stage(record, StageId.WRITE)
        content_b, meta_b, pageindex_b = artifacts_to_bytes(normalized)
        wrote_content = await write_artifact(spec, "content_md", content_b)
        wrote_meta = await write_artifact(spec, "meta_json", meta_b)
        wrote_pageindex = False
        if pageindex_b is not None:
            wrote_pageindex = await write_artifact(spec, "pageindex_json", pageindex_b)
        record.artifacts = JobArtifacts(
            content_md=wrote_content,
            meta_json=wrote_meta,
            pageindex_json=wrote_pageindex,
            ready=wrote_content and wrote_meta,
        )
        await self._finish_stage(
            record,
            StageId.WRITE,
            outputs={
                "content_md": wrote_content,
                "meta_json": wrote_meta,
                "pageindex_json": wrote_pageindex,
            },
        )

    async def _stage_finalize(self, record: JobRecord) -> None:
        await self._begin_stage(record, StageId.FINALIZE)
        if not record.artifacts.ready:
            raise RuntimeError("artifacts not fully written")
        await self._finish_stage(record, StageId.FINALIZE, outputs={"ready": True})

    async def _begin_stage(self, record: JobRecord, stage_id: StageId) -> None:
        await self.store.update_stage(record.job_id, stage_id, status=StageStatus.RUNNING)
        record = await self.store.get_job(record.job_id) or record
        record.current_stage = stage_id.value
        await self.store.save_job(record)
        await sender.emit_stage_updated(record)

    async def _finish_stage(
        self,
        record: JobRecord,
        stage_id: StageId,
        *,
        outputs: dict[str, Any] | None = None,
        status: StageStatus = StageStatus.SUCCEEDED,
    ) -> None:
        await self.store.update_stage(
            record.job_id,
            stage_id,
            status=status,
            outputs=outputs or {},
        )
        record = await self.store.get_job(record.job_id) or record
        await sender.emit_stage_updated(record)

    async def _skip_stage(self, record: JobRecord, stage_id: StageId, *, reason: str | None = None) -> None:
        outputs: dict[str, Any] = {}
        if reason:
            outputs["reason"] = reason
        await self.store.update_stage(
            record.job_id,
            stage_id,
            status=StageStatus.SKIPPED,
            outputs=outputs,
        )
        record = await self.store.get_job(record.job_id) or record
        await sender.emit_stage_updated(record)

    async def _update_stage_outputs(
        self,
        record: JobRecord,
        stage_id: StageId,
        *,
        outputs: dict[str, Any],
    ) -> None:
        await self.store.update_stage(
            record.job_id,
            stage_id,
            status=StageStatus.RUNNING,
            outputs=outputs,
        )
        record = await self.store.get_job(record.job_id) or record
        await sender.emit_stage_updated(record)
