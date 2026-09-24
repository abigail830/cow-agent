"""Helpers for cross-session document list (attachments + artifacts)."""

from __future__ import annotations

from typing import Any

from app.api.schemas import DocumentOut


def slim_artifact_spec_for_list(spec: dict[str, Any]) -> dict[str, Any]:
    """Drop heavy inline preview bodies from list responses."""
    slim = dict(spec)
    slim["content"] = ""
    return slim


def parse_artifact_spec(display: dict[str, Any] | None) -> dict[str, Any] | None:
    if not display:
        return None
    spec = display.get("spec")
    if not isinstance(spec, dict):
        return None
    artifact_id = spec.get("artifact_id") or spec.get("ref")
    if not artifact_id:
        return None
    return spec


def merge_document_pages(
    attachments: list[DocumentOut],
    artifacts: list[DocumentOut],
    *,
    offset: int,
    limit: int,
) -> list[DocumentOut]:
    """Merge two created_at-desc lists and slice a unified page."""
    merged = sorted(
        attachments + artifacts,
        key=lambda row: row.created_at or "",
        reverse=True,
    )
    return merged[offset : offset + limit]
