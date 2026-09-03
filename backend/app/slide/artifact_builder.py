"""Build and persist slide deck artifacts."""

from __future__ import annotations

import uuid
from typing import Any

from app.artifacts.spec import ArtifactSpec
from app.artifacts.storage import new_chat_artifact_id, save_slide_deck
from app.slide.dist_base import rewrite_slidev_dist_base
from app.slide.renderer import slugify_title

_PREVIEW_CHAR_LIMIT = 120_000


def artifact_download_url(chat_id: uuid.UUID, artifact_id: str, *, variant: str | None = None) -> str:
    base = f"/api/v1/chats/{chat_id}/artifacts/{artifact_id}"
    if variant:
        return f"{base}?format={variant}"
    return base


def artifact_preview_url(chat_id: uuid.UUID, artifact_id: str) -> str:
    return f"/api/v1/chats/{chat_id}/artifacts/{artifact_id}/preview/"


def build_slide_artifact_spec(
    *,
    title: str,
    source: str,
    chat_id: uuid.UUID | None,
    dist_files: dict[str, bytes],
    pdf_bytes: bytes | None,
) -> ArtifactSpec:
    artifact_id = new_chat_artifact_id(prefix="slide")
    filename_base = slugify_title(title)
    md_filename = f"{filename_base}.md"
    pdf_filename = f"{filename_base}.pdf"

    md_download_url = None
    pdf_download_url = None
    preview_url = None
    if chat_id is not None:
        preview_base = artifact_preview_url(chat_id, artifact_id)
        stored_dist = (
            rewrite_slidev_dist_base(dist_files, preview_base) if dist_files else dist_files
        )
        save_slide_deck(
            chat_id,
            artifact_id,
            source_md=source,
            filename=md_filename,
            dist_files=stored_dist,
            pdf_bytes=pdf_bytes,
        )
        md_download_url = artifact_download_url(chat_id, artifact_id)
        if dist_files:
            preview_url = artifact_preview_url(chat_id, artifact_id)
        if pdf_bytes:
            pdf_download_url = artifact_download_url(chat_id, artifact_id, variant="pdf")

    preview_truncated = len(source) > _PREVIEW_CHAR_LIMIT
    preview_content = "" if preview_truncated else source

    return ArtifactSpec(
        kind="slide_deck",
        title=title.strip() or "Slide deck",
        format="slidev",
        content=preview_content,
        filename=md_filename,
        artifact_id=artifact_id,
        download_url=md_download_url,
        pdf_download_url=pdf_download_url,
        pdf_filename=pdf_filename if pdf_bytes else None,
        preview_url=preview_url,
        preview_truncated=preview_truncated,
        source=source,
    )


def slide_tool_payload(spec: ArtifactSpec, *, build_logs: str = "", warning: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "queued",
        "preview_url": spec.preview_url,
        "download_url": spec.download_url,
        "pdf_download_url": spec.pdf_download_url,
        "filename": spec.filename,
        "format": spec.format,
        "artifact_id": spec.artifact_id,
    }
    if warning:
        payload["warning"] = warning
        payload["logs"] = build_logs
    return payload


def build_html_ppt_artifact_spec(
    *,
    title: str,
    source: str,
    chat_id: uuid.UUID | None,
    dist_files: dict[str, bytes],
) -> ArtifactSpec:
    artifact_id = new_chat_artifact_id(prefix="slide")
    filename_base = slugify_title(title)
    html_filename = f"{filename_base}.html"

    download_url = None
    preview_url = None
    if chat_id is not None:
        save_slide_deck(
            chat_id,
            artifact_id,
            source_md=source,
            filename=html_filename,
            dist_files=dist_files,
            deck_format="html",
        )
        download_url = artifact_download_url(chat_id, artifact_id)
        if dist_files:
            preview_url = artifact_preview_url(chat_id, artifact_id)

    preview_truncated = len(source) > _PREVIEW_CHAR_LIMIT
    preview_content = "" if preview_truncated else source

    return ArtifactSpec(
        kind="slide_deck",
        title=title.strip() or "Slide deck",
        format="html",
        content=preview_content,
        filename=html_filename,
        artifact_id=artifact_id,
        download_url=download_url,
        preview_url=preview_url,
        preview_truncated=preview_truncated,
        source=source,
    )
