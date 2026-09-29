"""Page-budget helpers — classify + PDF page count, no MAF assembly."""

from __future__ import annotations

import uuid
from typing import Any

from app.platform.attachments.convert.pdf_pages import count_pdf_pages
from app.platform.attachments.kinds import AttachmentKind, classify_attachment, page_cost_for_kind
from app.platform.attachments.source import attachment_materialize_source, hub_storage_user_id
from app.platform.attachments.storage import load_inline_attachment
from app.platform.document_hub.storage import load_hub_original


def _item_id(item: Any) -> str:
    return str(getattr(item, "id", None) or (item.get("id") if isinstance(item, dict) else "") or "")


def _item_attr(item: Any, name: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def load_attachment_bytes(item: Any, *, chat_id: uuid.UUID) -> bytes:
    raw_id = _item_id(item)
    if not raw_id:
        raise ValueError("Attachment is missing id")
    item_id = uuid.UUID(raw_id)
    if attachment_materialize_source(item) == "hub_item":
        user_id = hub_storage_user_id(item)
        try:
            return load_hub_original(user_id, item_id)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Document Hub original not found for item {raw_id}"
            ) from exc
    return load_inline_attachment(chat_id, item_id)


def attachment_page_cost(item: Any, *, chat_id: uuid.UUID | None = None) -> int:
    filename = str(_item_attr(item, "filename") or "attachment")
    mime_type = str(_item_attr(item, "mime_type") or "")
    kind = classify_attachment(filename=filename, mime_type=mime_type)
    if kind != AttachmentKind.PDF:
        return page_cost_for_kind(kind)
    if chat_id is None:
        return page_cost_for_kind(kind, pdf_pages=1)
    data = load_attachment_bytes(item, chat_id=chat_id)
    return page_cost_for_kind(kind, pdf_pages=count_pdf_pages(data))
