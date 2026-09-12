from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class ExtractedAttachment:
    attachment_id: uuid.UUID
    filename: str
    mime_type: str
    kind: Literal["text"] = "text"
    content: str = ""
    truncated: bool = False
    char_count: int = 0
    extract_ms: int = 0
    warnings: list[str] = field(default_factory=list)
