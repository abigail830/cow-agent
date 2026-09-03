"""Proposal Word export orchestration."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from app.proposal.draft import build_draft_preview
from app.proposal.loaders import load_template_yaml, template_dir
from app.proposal.storage import new_artifact_id, save_artifact
from app.proposal.word_context import build_word_context, word_export_filename
from app.proposal.word_render import render_word_document


class ProposalExportError(Exception):
    def __init__(self, code: str, message: str, *, http_status: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def word_template_path(template_id: str) -> Path | None:
    tpl = load_template_yaml(template_id)
    export_cfg = tpl.get("document_export") or {}
    if not isinstance(export_cfg, dict):
        return None
    word_cfg = export_cfg.get("word") or {}
    if not isinstance(word_cfg, dict):
        return None
    if word_cfg.get("enabled") is False:
        return None
    rel_path = str(word_cfg.get("template_file") or "export/proposal.docx").strip()
    path = (template_dir(template_id) / rel_path).resolve()
    root = template_dir(template_id).resolve()
    if not str(path).startswith(str(root)):
        return None
    return path if path.is_file() else None


def word_export_status(draft: dict[str, Any] | None) -> dict[str, Any]:
    if not draft:
        return {"available": False, "reason": "no_draft"}
    template_id = str((draft.get("meta") or {}).get("template_id") or "").strip()
    if not template_id:
        return {"available": False, "reason": "no_template_id"}
    path = word_template_path(template_id)
    if path is None:
        return {"available": False, "reason": "no_word_template"}
    return {"available": True, "template_file": str(path.name)}


def _artifact_download_url(chat_id: uuid.UUID, artifact_id: str) -> str:
    return f"/api/v1/chats/{chat_id}/artifacts/{artifact_id}"


def generate_proposal_docx(
    draft: dict[str, Any],
    *,
    chat_id: uuid.UUID | None = None,
    force: bool = False,
    persist: bool = True,
) -> dict[str, Any]:
    preview = build_draft_preview(draft)
    completeness = preview.get("completeness") or {}
    if not force and not completeness.get("ready_to_generate"):
        raise ProposalExportError(
            "blocked",
            "Proposal draft is not ready to generate.",
            http_status=422,
        )

    template_id = str((draft.get("meta") or {}).get("template_id") or "").strip()
    if not template_id:
        raise ProposalExportError("empty", "Proposal draft has no template_id.", http_status=422)

    template_path = word_template_path(template_id)
    if template_path is None:
        raise ProposalExportError(
            "no_word_template",
            f"Template {template_id!r} has no Word export template.",
            http_status=422,
        )

    context = build_word_context(draft)
    try:
        docx_bytes = render_word_document(template_path, context)
    except Exception as exc:
        message = str(exc).strip() or type(exc).__name__
        if "endfor" in message.lower() or "TemplateSyntaxError" in type(exc).__name__:
            message = (
                "Word template syntax error. Use {%tr for %} / {%tr endfor %} inside table rows, "
                "and do not mix with {% for row ... %} / {% endfor %}. "
                f"Detail: {message}"
            )
        raise ProposalExportError("template_render_error", message, http_status=422) from exc
    filename = word_export_filename(draft)
    title = str((draft.get("meta") or {}).get("title") or preview.get("title") or "Proposal")
    artifact_id = new_artifact_id()
    download_url = None
    if persist and chat_id is not None:
        save_artifact(
            chat_id,
            artifact_id,
            binary=docx_bytes,
            filename=filename,
            format="docx",
        )
        download_url = _artifact_download_url(chat_id, artifact_id)

    return {
        "status": "ok",
        "format": "docx",
        "artifact_id": artifact_id,
        "filename": filename,
        "download_url": download_url,
        "title": title,
        "state_fingerprint": preview.get("state_fingerprint") or "",
    }
