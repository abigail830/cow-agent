"""Attachment provenance for materialize / storage routing.

Document Hub items are never stored under chat inline paths. All materialize
code must branch on ``attachment_materialize_source`` — not on ``chat_id`` presence
in message metadata (hub rows include chat_id for the referencing conversation).

Provider-specific shortcuts (e.g. Claude ``pdf_file_id``) apply only to
``chat_attachment`` uploads that were registered with that provider's Files API.
They must not disable hydrate for ``hub_item`` references.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from app.platform.attachments.kinds import AttachmentKind, classify_attachment
from app.platform.docstore.blob import parsed_artifact_exists, parsed_artifact_exists_scoped
from app.platform.docstore.models import PARSE_READY_STATUSES
from app.platform.docstore.scope import DocumentScope

AttachmentSource = Literal["hub_item", "chat_attachment"]

HUB_ITEM_SOURCE = "hub_item"


def _item_attr(item: Any, name: str, default: Any = "") -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def attachment_materialize_source(item: Any) -> AttachmentSource:
    explicit = str(_item_attr(item, "source") or "").strip()
    if explicit == HUB_ITEM_SOURCE:
        return "hub_item"
    if str(_item_attr(item, "provider") or "").strip() == "hub":
        return "hub_item"
    folder_id = _item_attr(item, "folder_id", None)
    if folder_id not in (None, ""):
        return "hub_item"
    return "chat_attachment"


def is_hub_materialize_item(item: Any) -> bool:
    return attachment_materialize_source(item) == "hub_item"


def hub_storage_user_id(item: Any) -> uuid.UUID:
    raw = _item_attr(item, "user_id", None)
    if not raw:
        raise ValueError(
            "Hub document metadata is missing user_id; re-send the message or re-import from Document Hub."
        )
    return uuid.UUID(str(raw))


def explicit_parse_ready(item: Any) -> bool:
    status = _item_attr(item, "parse_status")
    if not status:
        return False
    return str(status) in PARSE_READY_STATUSES


def parsed_content_md_exists(
    item: Any,
    *,
    chat_id: uuid.UUID | None,
    source: AttachmentSource | None = None,
) -> bool:
    source = source or attachment_materialize_source(item)
    att_id = str(_item_attr(item, "id") or "").strip()
    if not att_id:
        return False
    try:
        if source == "hub_item":
            uid = hub_storage_user_id(item)
            return parsed_artifact_exists_scoped(
                DocumentScope.hub(uid, uuid.UUID(att_id)),
                "content_md",
            )
        if chat_id is not None:
            return parsed_artifact_exists(chat_id, uuid.UUID(att_id), "content_md")
    except (ValueError, FileNotFoundError):
        return False
    return False


def document_hydrate_kinds() -> frozenset[AttachmentKind]:
    return frozenset(
        {
            AttachmentKind.TEXT,
            AttachmentKind.SHEET,
            AttachmentKind.PDF,
            AttachmentKind.OFFICE,
            AttachmentKind.AUDIO,
        }
    )


def attachment_document_kind(item: Any) -> AttachmentKind:
    filename = str(_item_attr(item, "filename") or "attachment")
    mime_type = str(_item_attr(item, "mime_type") or "application/octet-stream")
    return classify_attachment(filename=filename, mime_type=mime_type)


class HubDocumentMaterializeError(ValueError):
    """Hub @ reference cannot be loaded from chat inline storage."""


def raise_if_hub_document_blocked_from_inline(item: Any) -> None:
    """P1: do not silently fall back to chat inline paths for parsed hub documents."""
    if not is_hub_materialize_item(item):
        return
    kind = attachment_document_kind(item)
    if kind not in document_hydrate_kinds():
        return
    filename = str(_item_attr(item, "filename") or "attachment")
    if not explicit_parse_ready(item):
        raise HubDocumentMaterializeError(
            f"Hub document «{filename}» is not parsed yet. "
            "Wait until Document Hub shows Ready, then @ reference again."
        )
    if parsed_content_md_exists(item, chat_id=None):
        return
    raise HubDocumentMaterializeError(
        f"Hub document «{filename}» is marked parse-ready but parsed markdown is missing. "
        "Re-run parse in Document Hub, then @ reference again."
    )


def block_hub_document_binary_materialize(item: Any) -> None:
    """Never inline Hub originals (PDF bytes / raster) — hydrate + doc tools only."""
    if not is_hub_materialize_item(item):
        return
    kind = attachment_document_kind(item)
    if kind not in document_hydrate_kinds():
        return
    raise_if_hub_document_blocked_from_inline(item)
    filename = str(_item_attr(item, "filename") or "attachment")
    raise HubDocumentMaterializeError(
        f"Hub document «{filename}» must use parse hydrate (attachment_grep / attachment_read), "
        "not inline file bytes."
    )
