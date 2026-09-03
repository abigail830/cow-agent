import uuid
from typing import Any

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


class ChatCreate(BaseModel):
    agent_id: uuid.UUID
    user_id: uuid.UUID | None = None
    title: str | None = None


class ChatOut(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    agent_id: uuid.UUID
    title: str | None


class ChatListOut(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    title: str | None
    created_at: str | None
    updated_at: str | None


class MessageCreate(BaseModel):
    content: str = ""
    attachment_ids: list[uuid.UUID] = Field(default_factory=list)


class AttachmentOut(BaseModel):
    id: uuid.UUID
    chat_id: uuid.UUID
    filename: str
    mime_type: str
    size_bytes: int
    provider: str
    provider_file_id: str
    created_at: str | None = None


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
