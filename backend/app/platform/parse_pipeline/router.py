from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.platform.attachments.kinds import AttachmentKind


class PipelineRoute(StrEnum):
    SKIP = "skip"
    REJECT = "reject"


@dataclass(frozen=True)
class PipelineResolution:
    action: str
    pipeline_id: str | None = None


def resolve_pipeline(kind: AttachmentKind) -> PipelineResolution:
    if kind == AttachmentKind.IMAGE:
        return PipelineResolution(action=PipelineRoute.SKIP.value)
    if kind == AttachmentKind.OFFICE:
        return PipelineResolution(action=PipelineRoute.REJECT.value)
    if kind == AttachmentKind.TEXT:
        return PipelineResolution(action="parse", pipeline_id="text_standard")
    if kind == AttachmentKind.SHEET:
        return PipelineResolution(action="parse", pipeline_id="sheet_standard")
    if kind == AttachmentKind.PDF:
        return PipelineResolution(action="parse", pipeline_id="pdf_standard")
    return PipelineResolution(action=PipelineRoute.REJECT.value)
