from __future__ import annotations

import uuid

from sqlalchemy import select

from app.db.models import AgentModel, Chat, ChatAttachment
from app.db.repositories.attachments import AttachmentRepository


def test_user_document_filters_always_scope_to_user_id():
    user_id = uuid.uuid4()
    repo = AttachmentRepository(session=None)  # type: ignore[arg-type]

    stmt = (
        select(ChatAttachment, Chat, AgentModel)
        .join(Chat, ChatAttachment.chat_id == Chat.id)
        .join(AgentModel, Chat.agent_id == AgentModel.id)
        .where(Chat.user_id == user_id)
    )
    compiled = str(
        repo._apply_user_document_filters(
            stmt,
            q="report",
            parse_status="ready",
            mime_type="application/pdf",
            agent_id=uuid.uuid4(),
        ).compile(compile_kwargs={"literal_binds": True})
    )

    assert "chats.user_id" in compiled
    assert user_id.hex in compiled
    assert "chat_attachments.filename" in compiled
    assert "parse_status" in compiled
    assert "chat_attachments.mime_type" in compiled
    assert "chats.agent_id" in compiled
