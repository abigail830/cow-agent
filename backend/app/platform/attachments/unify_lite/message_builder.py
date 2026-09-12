from __future__ import annotations

from agent_framework import Content, Message

from app.platform.attachments.unify_lite.pipeline import format_extracted_attachment_block
from app.platform.attachments.unify_lite.types import ExtractedAttachment


def build_user_run_input_lite(
    content: str,
    extracted: list[ExtractedAttachment],
    *,
    size_bytes_by_id: dict | None = None,
) -> str | Message:
    text = content.strip()
    if not extracted:
        return text

    sizes = size_bytes_by_id or {}
    blocks = [
        format_extracted_attachment_block(
            item,
            size_bytes=int(sizes.get(item.attachment_id, 0)),
        )
        for item in extracted
    ]
    attachment_section = "\n\n".join(blocks)
    sections: list[str] = []
    if text:
        sections.append(text)
    sections.append(f"---\n[Attachments — unify-lite]\n\n{attachment_section}\n---")
    merged = "\n\n".join(sections).strip()
    return Message(role="user", contents=[Content.from_text(merged)])
