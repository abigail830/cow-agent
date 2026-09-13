from __future__ import annotations

import uuid

from app.config import get_settings
from app.platform.attachments.attachment_storage import (
    load_inline_attachment,
    parse_inline_attachment_id,
)
from app.platform.attachments.unify_lite.extractors.registry import extract_bytes
from app.platform.attachments.unify_lite.truncate import truncate_chars
from app.platform.attachments.unify_lite.types import ExtractedAttachment


def _format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def extract_attachments(chat_id: uuid.UUID, rows: list) -> list[ExtractedAttachment]:
    settings = get_settings()
    max_per_file = settings.unify_lite_max_chars_per_file
    max_per_message = settings.unify_lite_max_chars_per_message

    extracted: list[ExtractedAttachment] = []
    for row in rows:
        attachment_id = parse_inline_attachment_id(row.provider_file_id)
        data = load_inline_attachment(chat_id, attachment_id)
        content, warnings, extract_ms = extract_bytes(
            filename=row.filename,
            mime_type=row.mime_type,
            data=data,
        )
        truncated = False
        if len(content) > max_per_file:
            content, truncated = truncate_chars(content, max_per_file)

        extracted.append(
            ExtractedAttachment(
                attachment_id=row.id,
                filename=row.filename,
                mime_type=row.mime_type,
                content=content,
                truncated=truncated,
                char_count=len(content),
                extract_ms=extract_ms,
                warnings=list(warnings),
            )
        )

    total_chars = sum(item.char_count for item in extracted)
    if total_chars <= max_per_message or not extracted:
        return extracted

    overflow = total_chars - max_per_message
    for index in range(len(extracted) - 1, -1, -1):
        if overflow <= 0:
            break
        item = extracted[index]
        new_limit = max(0, item.char_count - overflow)
        new_content, truncated = truncate_chars(item.content, new_limit)
        overflow -= item.char_count - len(new_content)
        extracted[index] = ExtractedAttachment(
            attachment_id=item.attachment_id,
            filename=item.filename,
            mime_type=item.mime_type,
            content=new_content,
            truncated=item.truncated or truncated,
            char_count=len(new_content),
            extract_ms=item.extract_ms,
            warnings=[*item.warnings, "shortened to fit message attachment budget"],
        )

    return extracted


def format_extracted_attachment_block(item: ExtractedAttachment, *, size_bytes: int) -> str:
    header = f"### {item.filename} ({item.mime_type}, {_format_size(size_bytes)})"
    if item.warnings:
        header += f"\n_Note: {'; '.join(item.warnings)}_"
    if item.truncated:
        header += "\n_Content truncated._"
    return f"{header}\n```\n{item.content}\n```"


def wrap_unify_lite_attachment_section(text_blocks: list[str]) -> str:
    """Format extracted attachment blocks into the unify-lite delimiter section."""
    if not text_blocks:
        return ""
    attachment_section = "\n\n".join(text_blocks)
    return f"---\n[Attachments — unify-lite]\n\n{attachment_section}\n---"
