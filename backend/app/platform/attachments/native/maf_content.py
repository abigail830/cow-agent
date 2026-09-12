"""Convert attachment DB rows / metadata into MAF Content blocks (native path)."""

from __future__ import annotations

import uuid

from agent_framework import Content

from app.platform.attachments.attachment_storage import (
    is_inline_provider_file_id,
    load_inline_attachment,
    parse_inline_attachment_id,
)


def attachment_to_maf_content(att) -> Content:
    provider_file_id = str(getattr(att, "provider_file_id", "") or "")
    mime_type = str(getattr(att, "mime_type", "") or "application/octet-stream")
    filename = str(getattr(att, "filename", "") or "attachment")

    if is_inline_provider_file_id(provider_file_id):
        chat_id = getattr(att, "chat_id", None)
        if chat_id is None:
            raise ValueError("Inline attachment is missing chat_id")
        attachment_id = parse_inline_attachment_id(provider_file_id)
        data = load_inline_attachment(chat_id, attachment_id)
        return Content.from_data(
            data=data,
            media_type=mime_type,
            additional_properties={"filename": filename},
        )

    return Content.from_hosted_file(
        file_id=provider_file_id,
        media_type=mime_type,
        name=filename,
    )


def metadata_attachment_to_maf_content(item: dict, *, chat_id: uuid.UUID) -> Content | None:
    file_id = item.get("provider_file_id")
    if not file_id:
        return None
    mime_type = str(item.get("mime_type") or "application/octet-stream")
    filename = str(item.get("filename") or "attachment")
    if is_inline_provider_file_id(str(file_id)):
        attachment_id = uuid.UUID(str(item.get("id") or parse_inline_attachment_id(str(file_id))))
        data = load_inline_attachment(chat_id, attachment_id)
        return Content.from_data(
            data=data,
            media_type=mime_type,
            additional_properties={"filename": filename},
        )
    return Content.from_hosted_file(
        file_id=str(file_id),
        media_type=mime_type,
        name=filename,
    )


def attachments_to_maf_contents(attachments: list) -> list[Content]:
    return [attachment_to_maf_content(att) for att in attachments]


def attachment_metadata(att, *, processing_mode: str | None = None) -> dict:
    payload = {
        "id": str(att.id),
        "filename": att.filename,
        "mime_type": att.mime_type,
        "size_bytes": att.size_bytes,
        "provider": att.provider,
        "provider_file_id": att.provider_file_id,
    }
    if processing_mode:
        payload["processing_mode"] = processing_mode
    return payload
