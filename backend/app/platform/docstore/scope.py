"""Document storage scope for chat attachments vs Document Hub."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

DocumentScopeKind = Literal["chat", "hub"]


@dataclass(frozen=True)
class DocumentScope:
    kind: DocumentScopeKind
    scope_id: uuid.UUID
    document_id: uuid.UUID

    @classmethod
    def chat(cls, chat_id: uuid.UUID, attachment_id: uuid.UUID) -> DocumentScope:
        return cls(kind="chat", scope_id=chat_id, document_id=attachment_id)

    @classmethod
    def hub(cls, user_id: uuid.UUID, item_id: uuid.UUID) -> DocumentScope:
        return cls(kind="hub", scope_id=user_id, document_id=item_id)
