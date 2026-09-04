"""Build chat artifacts from Content Studio sandbox deliverables."""

from __future__ import annotations

import uuid
from pathlib import PurePosixPath

from app.shared.artifacts.spec import ArtifactSpec
from app.shared.artifacts.storage import new_chat_artifact_id, save_content_file, save_slide_deck
from app.agent_specific.slide.artifact_builder import artifact_download_url, artifact_preview_url
from app.agent_specific.slide.renderer import slugify_title

_PREVIEW_CHAR_LIMIT = 120_000


def _format_for_path(path: str) -> tuple[str, str]:
    suffix = PurePosixPath(path).suffix.lower()
    if suffix == ".docx":
        return "content_document", "docx"
    if suffix == ".pptx":
        return "content_document", "pptx"
    if suffix == ".html":
        return "slide_deck", "html"
    if suffix == ".md":
        return "content_document", "markdown"
    return "content_document", "markdown"


def build_content_studio_artifact_spec(
    *,
    sandbox_path: str,
    file_bytes: bytes,
    title: str,
    chat_id: uuid.UUID | None,
) -> ArtifactSpec:
    filename = PurePosixPath(sandbox_path).name or "deliverable"
    kind, fmt = _format_for_path(filename)
    artifact_id = new_chat_artifact_id(prefix="content")
    card_title = (title or "").strip() or filename

    download_url = None
    preview_url = None
    preview_content = ""
    preview_truncated = False

    if chat_id is not None:
        if fmt == "html":
            html_text = file_bytes.decode("utf-8", errors="replace")
            save_slide_deck(
                chat_id,
                artifact_id,
                source_md=html_text,
                filename=filename,
                dist_files={"index.html": file_bytes},
                deck_format="html",
            )
            download_url = artifact_download_url(chat_id, artifact_id)
            preview_url = artifact_preview_url(chat_id, artifact_id)
            preview_truncated = len(html_text) > _PREVIEW_CHAR_LIMIT
            preview_content = "" if preview_truncated else html_text
        else:
            save_content_file(
                chat_id,
                artifact_id,
                data=file_bytes,
                filename=filename,
                file_format=fmt,  # type: ignore[arg-type]
            )
            download_url = artifact_download_url(chat_id, artifact_id)

        return ArtifactSpec(
            kind=kind,  # type: ignore[arg-type]
            title=card_title,
            format=fmt,  # type: ignore[arg-type]
            content=preview_content,
            filename=filename,
            artifact_id=artifact_id,
            download_url=download_url,
            preview_url=preview_url,
            preview_truncated=preview_truncated,
        )

    return ArtifactSpec(
        kind=kind,  # type: ignore[arg-type]
        title=card_title,
        format=fmt,  # type: ignore[arg-type]
        content="",
        filename=filename,
        artifact_id=artifact_id,
    )
