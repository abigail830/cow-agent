"""Turn manifest and chat library index for Hydrate."""

from __future__ import annotations

import uuid
from typing import Any

from app.config import get_settings
from app.platform.doc_retrieval.context import ChatAttachmentIndexEntry, DocRetrievalContext
from app.platform.doc_retrieval.store import cached_meta, is_document_kind, load_content_md


def _section_preview(meta: dict[str, Any], *, max_items: int = 8) -> str:
    sections = meta.get("sections") or []
    if not isinstance(sections, list) or not sections:
        return ""
    labels: list[str] = []
    for section in sections[:max_items]:
        if not isinstance(section, dict):
            continue
        title = str(section.get("title") or "").strip()
        sid = str(section.get("id") or "")
        if title and sid:
            labels.append(f"{sid} {title}")
        elif title:
            labels.append(title)
    if len(sections) > max_items:
        labels.append("…")
    return ", ".join(labels)


def _preview_snippet(content: str, *, max_bytes: int) -> str:
    if max_bytes <= 0 or not content:
        return ""
    encoded = content.encode("utf-8")
    if len(encoded) <= max_bytes:
        return content.strip()
    return encoded[:max_bytes].decode("utf-8", errors="ignore").strip() + "…"


def build_turn_attachment_block(
    entry: ChatAttachmentIndexEntry,
    meta: dict[str, Any] | None,
    *,
    preview_max_bytes: int,
    content_preview: str | None = None,
) -> str:
    page_part = f", {entry.page_count} pages" if entry.page_count else ""
    line_part = f", {entry.line_count} lines" if entry.line_count and not entry.page_count else ""
    figure_part = f", {entry.figure_count} figures" if entry.figure_count else ""
    lines = [
        f"- {entry.filename} (attachment_id={entry.attachment_id}, {entry.kind}{page_part}{line_part}{figure_part})",
    ]
    if meta:
        sections = _section_preview(meta)
        if sections:
            lines.append(f"  Sections: [{sections}]")
        if entry.figure_count:
            lines.append("  Figures: use attachment_read_figure for figure:fN refs in content")
    lines.append("  Tools: attachment_grep → attachment_read → attachment_read_figure (for figure:fN)")
    if preview_max_bytes > 0 and content_preview:
        snippet = _preview_snippet(content_preview, max_bytes=preview_max_bytes)
        if snippet:
            lines.append(f"  Preview:\n```\n{snippet}\n```")
    return "\n".join(lines)


def build_turn_manifest_text(
    items: list[Any],
    *,
    ctx: DocRetrievalContext | None = None,
    chat_id=None,
) -> str:
    settings = get_settings()
    preview_max = settings.hydrate_preview_max_bytes
    blocks: list[str] = ["### Attachments this message"]
    for item in items:
        att_id = str(getattr(item, "id", None) or (item.get("id") if isinstance(item, dict) else "") or "").strip()
        if not att_id:
            continue
        entry = ctx.library.get(att_id) if ctx else None
        if entry is None:
            filename = str(getattr(item, "filename", None) or (item.get("filename") if isinstance(item, dict) else "attachment"))
            blocks.append(f"- {filename} (attachment_id={att_id})")
            continue
        meta = None
        content_preview = None
        if ctx and is_document_kind(entry.kind):
            try:
                att_uuid = uuid.UUID(att_id)
                meta = cached_meta(ctx, att_uuid)
                content_preview = load_content_md(ctx.chat_id, att_uuid)
            except Exception:
                meta = None
        blocks.append(
            build_turn_attachment_block(
                entry,
                meta,
                preview_max_bytes=preview_max,
                content_preview=content_preview,
            )
        )
    if len(blocks) == 1:
        return ""
    return "\n".join(blocks)


def build_library_index_text(ctx: DocRetrievalContext | None) -> str:
    if ctx is None or not ctx.library:
        return ""
    settings = get_settings()
    max_items = settings.hydrate_library_max_items
    entries = sorted(
        ctx.library.values(),
        key=lambda entry: entry.created_at or "",
        reverse=True,
    )
    lines = ["### Chat attachment library"]
    shown = entries[:max_items]
    for entry in shown:
        page_part = f"{entry.page_count}p" if entry.page_count else f"{entry.line_count}L" if entry.line_count else "-"
        fig_part = f", fig={entry.figure_count}" if entry.figure_count else ""
        lines.append(
            f"| {entry.attachment_id[:8]}… | {entry.filename} | {entry.kind} | {page_part}{fig_part} |"
        )
    if len(entries) > max_items:
        lines.append(f"_…and {len(entries) - max_items} more. Use attachment_list_chat._")
    lines.append("_Use attachment_find when the attachment id is unclear._")
    return "\n".join(lines)


def build_hydrate_text(
    items: list[Any],
    *,
    ctx: DocRetrievalContext | None = None,
) -> str:
    parts: list[str] = []
    turn = build_turn_manifest_text(items, ctx=ctx)
    if turn:
        parts.append(turn)
    library = build_library_index_text(ctx)
    if library:
        parts.append(library)
    return "\n\n".join(parts)
