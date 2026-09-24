import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class UserCreate(BaseModel):
    email: str
    name: str | None = None


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    name: str | None = None


class AgentOut(BaseModel):
    id: uuid.UUID
    slug: str | None = None
    name: str
    description: str | None
    model_provider: str
    model_name: str
    default_model_id: str | None = None
    selected_model_id: str | None = None
    supports_kb_scope: bool = False


class AgentModelSelectionIn(BaseModel):
    model_id: str


class AgentKbPreferenceOut(BaseModel):
    disabled_kb_ids: list[str] = Field(default_factory=list)


class AgentKbPreferenceIn(BaseModel):
    disabled_kb_ids: list[str] = Field(default_factory=list)


class KnowledgeBaseOut(BaseModel):
    id: str
    name: str
    description: str | None = None
    type: str | None = None
    item_count: int | None = None
    is_configured: bool | None = None
    enabled: bool = True


class KnowledgeBaseListOut(BaseModel):
    connected: bool
    items: list[KnowledgeBaseOut] = Field(default_factory=list)
    disabled_kb_ids: list[str] = Field(default_factory=list)
    message: str | None = None


class ModelOut(BaseModel):
    id: str
    label: str
    provider: str
    supports_attachments: bool = True
    available: bool = True


class ChatCreate(BaseModel):
    agent_id: uuid.UUID
    user_id: uuid.UUID | None = None
    title: str | None = None


class ContextUsageOut(BaseModel):
    tokens: int
    budget_tokens: int
    percent: float


class ChatOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    agent_id: uuid.UUID
    title: str | None


class ChatForkSourceOut(BaseModel):
    chat_id: uuid.UUID
    title: str | None


class ChatForkOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    agent_id: uuid.UUID
    title: str | None
    forked_from: ChatForkSourceOut


class ChatListOut(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    title: str | None
    created_at: str | None
    updated_at: str | None


class MessageCreate(BaseModel):
    content: str = ""
    attachment_ids: list[uuid.UUID] = Field(default_factory=list)


class ParseStageOut(BaseModel):
    stage_id: str | None = None
    status: str | None = None


class ParseProgressOut(BaseModel):
    current_stage: str | None = None
    message: str | None = None
    stages: list[ParseStageOut] | None = None


class AttachmentOut(BaseModel):
    id: uuid.UUID
    chat_id: uuid.UUID
    filename: str
    mime_type: str
    size_bytes: int
    provider: str
    provider_file_id: str
    created_at: str | None = None
    parse_status: Literal["pending", "running", "ready", "failed", "skipped"] = "ready"
    parse_pipeline_id: str | None = None
    parse_job_id: str | None = None
    parse_error_message: str | None = None
    parse_progress: ParseProgressOut | None = None


class ParsedArtifactsOut(BaseModel):
    content_md: bool = False
    meta_json: bool = False
    pageindex_json: bool = False


class DocumentOut(BaseModel):
    source_type: Literal["attachment", "artifact"] = "attachment"
    id: uuid.UUID
    chat_id: uuid.UUID
    filename: str
    created_at: str | None = None
    agent_id: uuid.UUID
    agent_name: str
    agent_slug: str | None = None
    chat_title: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    provider: str | None = None
    provider_file_id: str | None = None
    parse_status: Literal["pending", "running", "ready", "failed", "skipped"] | None = None
    parse_pipeline_id: str | None = None
    parse_job_id: str | None = None
    parse_error_message: str | None = None
    parse_progress: ParseProgressOut | None = None
    has_parsed_content: bool = False
    parsed_artifacts: ParsedArtifactsOut = Field(default_factory=ParsedArtifactsOut)
    artifact_id: str | None = None
    artifact_kind: str | None = None
    artifact_format: str | None = None
    artifact_spec: dict[str, Any] | None = None


class DocumentListOut(BaseModel):
    items: list[DocumentOut] = Field(default_factory=list)
    total: int = 0


class MessageOut(BaseModel):
    id: str
    chat_id: str
    role: str
    message_type: str
    content: str | None
    metadata: dict[str, Any]
    parent_id: str | None
    sequence: int
    created_at: str | None


class UiAnnotationOut(BaseModel):
    kind: str
    ref: str
    display: dict[str, Any] = Field(default_factory=dict)
    anchor_message_id: str | None = None


class TimelineMessageItemOut(BaseModel):
    kind: Literal["message"]
    id: str
    sequence: int
    turn_id: str
    message: dict[str, Any]
    created_at: str | None = None


class TimelineAnnotationItemOut(BaseModel):
    kind: Literal["ui_annotation"]
    id: str
    sequence: int
    turn_id: str
    annotation: UiAnnotationOut
    created_at: str | None = None


class ChatRunOut(BaseModel):
    id: str
    status: str
    error: str | None = None
    user_message_id: str | None = None
    model_id: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class ChatTimelineOut(BaseModel):
    chat_id: str
    items: list[TimelineMessageItemOut | TimelineAnnotationItemOut]
    runs: list[ChatRunOut] = Field(default_factory=list)


class ProposalCompletenessOut(BaseModel):
    missing_required: list[str] = Field(default_factory=list)
    ready_to_preview: bool = False
    ready_to_generate: bool = False


class ProposalExportWordStatusOut(BaseModel):
    available: bool = False
    reason: str | None = None
    template_file: str | None = None


class ProposalExportFormatsOut(BaseModel):
    word: ProposalExportWordStatusOut = Field(default_factory=ProposalExportWordStatusOut)


class ProposalPreviewOut(BaseModel):
    chat_id: str | None = None
    status: str
    title: str
    markdown: str = ""
    filename: str = "proposal.md"
    state_fingerprint: str
    message: str | None = None
    completeness: ProposalCompletenessOut = Field(default_factory=ProposalCompletenessOut)
    export: ProposalExportFormatsOut = Field(default_factory=ProposalExportFormatsOut)


class ProposalExportRequest(BaseModel):
    format: str = "docx"
    force: bool = False


class ProposalExportOut(BaseModel):
    status: str
    format: str
    artifact_id: str
    filename: str
    download_url: str | None = None
    title: str
    state_fingerprint: str
    missing_required: list[str] = Field(default_factory=list)


class ProposalDraftOut(BaseModel):
    chat_id: str
    draft: dict[str, Any]
    state_fingerprint: str


class FulfillmentFormsOut(BaseModel):
    chat_id: str
    forms: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0


class FulfillmentFormPatchIn(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class FulfillmentFormOut(BaseModel):
    status: str
    form: dict[str, Any]
    fulfillment_item: dict[str, Any] | None = None


class MemoryBulletOut(BaseModel):
    prefix: str
    text: str
    line: str
    kind: str


class MemoryOut(BaseModel):
    scope: str
    agent_id: uuid.UUID | None = None
    content: str
    revision: int
    bullets: list[MemoryBulletOut] = Field(default_factory=list)
    updated_at: str | None = None


class MemoryReplaceIn(BaseModel):
    content: str = ""


class MemoryAppendIn(BaseModel):
    scope: str
    agent_id: uuid.UUID | None = None
    lines: list[str]
    is_constraint: bool = False
    source: str = "ui"


class MemoryRemoveIn(BaseModel):
    scope: str
    agent_id: uuid.UUID | None = None
    match: str
    also_search_user: bool = False
