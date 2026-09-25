from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field

from parse_pipeline.schemas.stages import StageRecord


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineId(StrEnum):
    TEXT_STANDARD = "text_standard"
    PDF_STANDARD = "pdf_standard"
    OFFICE_STANDARD = "office_standard"
    SHEET_STANDARD = "sheet_standard"
    DOCUMENT_MIND_GENERIC = "document_mind_generic"


class DocumentMindOptions(BaseModel):
    llm_enhancement: bool = True
    enhancement_mode: str | None = "VLM"
    # DM API OutputFormat: markdown | visualLayoutInfo (see document_mind/client.py)
    output_formats: list[str] = Field(default_factory=lambda: ["markdown", "visualLayoutInfo"])


class OfficeOptions(BaseModel):
    markitdown_enabled: bool | None = None


class JobOptions(BaseModel):
    max_pages: int | None = 50
    table_max_rows_per_sheet: int = 2000
    office: OfficeOptions = Field(default_factory=OfficeOptions)
    document_mind: DocumentMindOptions = Field(default_factory=DocumentMindOptions)


class JobSource(BaseModel):
    source_type: str = "unknown"
    source_id: str | None = None
    tenant_id: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    content_hash: str | None = None


class JobCallbacks(BaseModel):
    webhook_url: str | None = None
    webhook_secret: str | None = None
    events: list[str] = Field(
        default_factory=lambda: ["stage.updated", "job.completed", "job.failed"]
    )


class SubmitJobRequest(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    idempotency_key: str | None = None
    pipeline_id: PipelineId | str
    storage: dict[str, Any]
    source: JobSource = Field(default_factory=JobSource)
    options: JobOptions = Field(default_factory=JobOptions)
    callbacks: JobCallbacks = Field(default_factory=JobCallbacks)


class JobProgress(BaseModel):
    percent: int | None = None
    message: str | None = None


class JobArtifacts(BaseModel):
    content_md: bool = False
    meta_json: bool = False
    pageindex_json: bool = False
    ready: bool = False


class JobError(BaseModel):
    code: str
    message: str
    stage_id: str | None = None


class JobResponse(BaseModel):
    job_id: str
    schema_version: Literal["1.0"] = "1.0"
    status: JobStatus
    pipeline_id: str
    caller_id: str | None = None
    provider_id: str | None = None
    current_stage: str | None = None
    progress: JobProgress | None = None
    stages: list[StageRecord] = Field(default_factory=list)
    artifacts: JobArtifacts = Field(default_factory=JobArtifacts)
    error: JobError | None = None
    stats: dict[str, Any] | None = None


class SubmitJobResponse(BaseModel):
    job_id: str
    status: JobStatus
