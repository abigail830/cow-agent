from __future__ import annotations

import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable

from parse_pipeline.config import Settings, get_settings
from parse_pipeline.job_store.base import JobRecord
from parse_pipeline.job_store.factory import get_job_store
from parse_pipeline.normalize.artifacts import NormalizedArtifacts, normalize_text_artifacts
from parse_pipeline.normalize.finalize import finalize_normalized_artifacts, finalize_office_markitdown_artifacts
from parse_pipeline.orchestrator.errors import job_error_from_exception
from parse_pipeline.providers.local.markitdown_office import extract_docx_markdown
from parse_pipeline.providers.local.sheet import extract_sheet_bytes
from parse_pipeline.providers.local.text import extract_text_bytes
from parse_pipeline.providers.document_mind.client import DEFAULT_OUTPUT_FORMATS
from parse_pipeline.quality.office_gate import GateDecision, evaluate_office_markdown
from parse_pipeline.quality.docx_probe import probe_docx_bytes
from parse_pipeline.schemas.job import JobArtifacts, JobError, JobProgress, JobStatus, PipelineId
from parse_pipeline.schemas.stages import StageId, StageStatus
from parse_pipeline.schemas.storage import StorageSpec
from parse_pipeline.storage.io import fetch_bytes, parse_storage_spec, write_normalized_artifacts
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
            try:
                record.error = job_error_from_exception(exc, record.current_stage)
            except Exception:
                record.error = JobError(
                    code="PARSE_FAILED",
                    message=str(exc) or type(exc).__name__,
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

    def _office_markitdown_enabled(self, record: JobRecord, filename: str) -> bool:
        office_opts = (record.options or {}).get("office") or {}
        enabled = office_opts.get("markitdown_enabled")
        if enabled is None:
            enabled = self.settings.office_markitdown_enabled
        return Path(filename).suffix.lower() == ".docx" and bool(enabled)

    async def _maybe_skip_analyze(self, record: JobRecord, pipeline_id: str) -> None:
        reason = None
        filename = record.source.get("filename") or ""
        if pipeline_id == PipelineId.OFFICE_STANDARD.value:
            if self._office_markitdown_enabled(record, filename):
                reason = "local_office_no_analyze"
            else:
                reason = "office_dm_only_v1"
        elif pipeline_id in {
            PipelineId.PDF_STANDARD.value,
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
        if pipeline_id == PipelineId.OFFICE_STANDARD.value:
            return await self._parse_office(record, file_bytes, filename)
        if pipeline_id in {
            PipelineId.PDF_STANDARD.value,
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

    def _office_dm_fallback_options(self, record: JobRecord) -> dict[str, Any]:
        options = dict(record.options or {})
        dm_opts = dict(options.get("document_mind") or {})
        dm_opts["llm_enhancement"] = False
        dm_opts["enhancement_mode"] = None
        dm_opts["output_formats"] = ["markdown", "visualLayoutInfo"]
        options["document_mind"] = dm_opts
        return options

    async def _parse_office(
        self,
        record: JobRecord,
        file_bytes: bytes,
        filename: str,
    ) -> NormalizedArtifacts:
        if not self._office_markitdown_enabled(record, filename):
            return await self._parse_document_mind(
                record,
                file_bytes,
                filename,
                record.pipeline_id,
            )

        import asyncio

        await self._skip_stage(record, StageId.PARSE_SUBMIT, reason="sync_local")
        await self._skip_stage(record, StageId.PARSE_WAIT, reason="sync_local")
        await self._begin_stage(record, StageId.PARSE_COLLECT)

        probe = await asyncio.to_thread(probe_docx_bytes, file_bytes)
        converter_ok = True
        converter_error: str | None = None
        content = ""
        conv_warnings: list[str] = []

        try:
            content, conv_warnings = await asyncio.to_thread(extract_docx_markdown, file_bytes)
        except Exception as exc:
            converter_ok = False
            converter_error = str(exc)
            logger.warning("markitdown office failed job_id=%s: %s", record.job_id, exc)

        gate = evaluate_office_markdown(
            content,
            probe=probe,
            converter_ok=converter_ok,
            converter_error=converter_error,
        )

        if gate.decision == GateDecision.FALLBACK:
            await self._finish_stage(
                record,
                StageId.PARSE_COLLECT,
                status=StageStatus.SKIPPED,
                outputs={
                    "provider_id": "markitdown",
                    "fallback": "document_mind",
                    "gate_decision": gate.decision.value,
                    "gate_grade": gate.grade.value,
                    "parse_score": gate.parse_score,
                    "gate_reasons": gate.fallback_reasons(),
                },
            )
            fallback_options = self._office_dm_fallback_options(record)
            artifacts = await self._parse_document_mind(
                record,
                file_bytes,
                filename,
                record.pipeline_id,
                job_options=fallback_options,
            )
            meta = dict(artifacts.meta_json)
            warnings = list(meta.get("warnings") or [])
            reasons = gate.fallback_reasons()
            if reasons:
                warnings.append(f"office_gate_fallback:{','.join(reasons)}")
            meta["warnings"] = warnings
            meta["fallback_from"] = "markitdown"
            meta["gate"] = {
                "decision": gate.decision.value,
                "grade": gate.grade.value,
                "parse_score": gate.parse_score,
                "checks": [asdict(c) for c in gate.checks],
            }
            artifacts.meta_json = meta
            artifacts.warnings = warnings
            return artifacts

        await self._finish_stage(
            record,
            StageId.PARSE_COLLECT,
            outputs={
                "provider_id": "markitdown",
                "gate_decision": gate.decision.value,
                "gate_grade": gate.grade.value,
                "parse_score": gate.parse_score,
                "line_count": content.count("\n") + (1 if content and not content.endswith("\n") else 0),
            },
        )
        record.provider_id = "markitdown"
        warnings = list(conv_warnings)
        artifacts = normalize_text_artifacts(
            content=content,
            job_id=record.job_id,
            pipeline_id=record.pipeline_id,
            parse_engine="markitdown",
            provider_id="markitdown",
            warnings=warnings,
        )
        meta = dict(artifacts.meta_json)
        meta["gate"] = {
            "decision": gate.decision.value,
            "grade": gate.grade.value,
            "parse_score": gate.parse_score,
            "checks": [asdict(c) for c in gate.checks],
        }
        artifacts.meta_json = meta
        artifacts.docx_probe = probe
        artifacts.office_source_bytes = file_bytes
        return artifacts

    async def _parse_document_mind(
        self,
        record: JobRecord,
        file_bytes: bytes,
        filename: str,
        pipeline_id: str,
        *,
        job_options: dict[str, Any] | None = None,
    ) -> NormalizedArtifacts:
        import asyncio

        from parse_pipeline.providers.document_mind.client import build_client_from_settings

        record.provider_id = "document_mind"
        if not self.settings.document_mind_configured:
            raise RuntimeError("Document Mind credentials not configured (DOCUMENT_MIND_ACCESS_KEY_ID/SECRET)")

        effective_options = job_options if job_options is not None else record.options
        client = build_client_from_settings(self.settings, effective_options)
        dm_opts = (effective_options or {}).get("document_mind") or {}
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
        import asyncio

        await self._begin_stage(record, StageId.NORMALIZE)
        try:
            if normalized.meta_json.get("parse_engine") == "markitdown":
                normalized = await asyncio.to_thread(finalize_office_markitdown_artifacts, normalized)
            else:
                normalized = await asyncio.to_thread(finalize_normalized_artifacts, normalized)
        except Exception as exc:
            logger.warning("normalize degraded job_id=%s: %s", record.job_id, exc)
            warning = f"normalize_failed:{exc}"
            warnings = list(normalized.warnings or [])
            warnings.append(warning)
            normalized.warnings = warnings
            meta = dict(normalized.meta_json)
            meta["warnings"] = list(meta.get("warnings") or []) + [warning]
            normalized.meta_json = meta
        await self._finish_stage(
            record,
            StageId.NORMALIZE,
            outputs={
                "line_count": normalized.meta_json.get("line_count"),
                "page_count": normalized.meta_json.get("page_count"),
                "figure_count": len(normalized.figure_files),
            },
        )
        return normalized

    async def _stage_write(self, record: JobRecord, spec: StorageSpec, normalized: NormalizedArtifacts) -> None:
        await self._begin_stage(record, StageId.WRITE)
        write_result = await write_normalized_artifacts(spec, normalized)
        record.artifacts = JobArtifacts(
            content_md=write_result.wrote_content,
            meta_json=write_result.wrote_meta,
            pageindex_json=write_result.wrote_pageindex,
            ready=write_result.wrote_content and write_result.wrote_meta,
        )
        await self._finish_stage(
            record,
            StageId.WRITE,
            outputs={
                "content_md": write_result.wrote_content,
                "meta_json": write_result.wrote_meta,
                "pageindex_json": write_result.wrote_pageindex,
                "figure_writes": write_result.figure_writes,
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
