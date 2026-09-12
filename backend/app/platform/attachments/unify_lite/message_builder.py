from __future__ import annotations

from agent_framework import Content, Message

from app.platform.attachments.native.maf_content import attachments_to_maf_contents
from app.platform.attachments.unify_lite.pipeline import format_extracted_attachment_block
from app.platform.attachments.unify_lite.types import ExtractedAttachment


def build_user_run_input_lite(
    content: str,
    extracted: list[ExtractedAttachment],
    *,
    image_attachments: list | None = None,
    size_bytes_by_id: dict | None = None,
) -> str | Message:
    """Build user input: extracted text blocks plus native vision for referenced images."""
    text = content.strip()
    images = list(image_attachments or [])
    sizes = size_bytes_by_id or {}

    text_blocks = [
        format_extracted_attachment_block(
            item,
            size_bytes=int(sizes.get(item.attachment_id, 0)),
        )
        for item in extracted
    ]

    if not text and not text_blocks and not images:
        return text

    contents: list[Content] = []
    sections: list[str] = []
    if text:
        sections.append(text)
    if text_blocks:
        attachment_section = "\n\n".join(text_blocks)
        sections.append(f"---\n[Attachments — unify-lite]\n\n{attachment_section}\n---")
    if sections:
        contents.append(Content.from_text("\n\n".join(sections).strip()))

    if images:
        contents.extend(attachments_to_maf_contents(images))

    if not contents:
        return text
    if len(contents) == 1 and not images:
        return Message(role="user", contents=contents)
    return Message(role="user", contents=contents)
