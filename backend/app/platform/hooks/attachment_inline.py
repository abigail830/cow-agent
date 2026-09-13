"""Inject pending inline attachments before each orchestrator LLM call."""

from __future__ import annotations

import logging
import uuid

from agent_framework import ChatContext, ChatMiddleware, Content, Message

from app.platform.attachments.attachment_storage import load_inline_attachment, parse_inline_attachment_id
from app.platform.attachments.visibility_constants import VISIBILITY_INLINED
from app.platform.attachments.run_state import get_attachment_run_state
from app.platform.attachments.unify_lite.pipeline import format_extracted_attachment_block, wrap_unify_lite_attachment_section
from app.platform.attachments.unify_lite.types import ExtractedAttachment
from app.platform.attachments.unify_lite.validation import is_unify_lite_image, is_unify_lite_text

logger = logging.getLogger(__name__)


def _inline_contents_for_attachment(*, chat_id: uuid.UUID, record) -> list[Content]:
    provider_file_id = str(record.provider_file_id or "")
    mime_type = str(record.mime_type or "application/octet-stream")
    filename = str(record.filename or "attachment")
    blob_id = parse_inline_attachment_id(provider_file_id)
    data = load_inline_attachment(chat_id, blob_id)

    if is_unify_lite_image(filename=filename, mime_type=mime_type):
        return [
            Content.from_data(
                data=data,
                media_type=mime_type,
                additional_properties={"filename": filename},
            )
        ]

    if is_unify_lite_text(filename=filename, mime_type=mime_type):
        text = data.decode("utf-8", errors="replace")
        extracted = ExtractedAttachment(
            attachment_id=record.attachment_id,
            filename=filename,
            mime_type=mime_type,
            content=text,
            truncated=False,
            char_count=len(text),
        )
        block = format_extracted_attachment_block(extracted, size_bytes=len(data))
        section = wrap_unify_lite_attachment_section([block])
        return [Content.from_text(section)]

    return [
        Content.from_text(
            f"[Attachment inline: {filename} — binary type {mime_type}; use read_attachment if needed.]"
        )
    ]


class AttachmentInlineChatMiddleware(ChatMiddleware):
    """Append pending inline_attachment payloads to chat messages before the model call."""

    async def process(self, context: ChatContext, call_next) -> None:
        state = get_attachment_run_state()
        if state is not None and state.pending_inline:
            scheduled = [
                att_id for att_id, status in list(state.pending_inline.items()) if status == "scheduled"
            ]
            if scheduled:
                contents: list[Content] = []
                for att_id in scheduled:
                    if att_id in state.injected_inline_ids:
                        state.pending_inline.pop(att_id, None)
                        continue
                    record = state.attachments.get(att_id)
                    if record is None:
                        continue
                    try:
                        contents.extend(
                            _inline_contents_for_attachment(chat_id=state.chat_id, record=record)
                        )
                        state.injected_inline_ids.add(att_id)
                        state.turn_visibility[att_id] = VISIBILITY_INLINED
                        state.pending_inline.pop(att_id, None)
                    except (OSError, ValueError) as exc:
                        logger.warning("attachment_inline_failed", extra={"attachment_id": att_id, "error": str(exc)})

                if contents:
                    supplement = Message(
                        role="user",
                        contents=[
                            Content.from_text("[Attachment inline supplement — platform injected per inline_attachment tool]"),
                            *contents,
                        ],
                    )
                    context.messages = list(context.messages or []) + [supplement]

        await call_next()
