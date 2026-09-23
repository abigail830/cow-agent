"""Load mirrored figures for vision tool responses."""

from __future__ import annotations

import base64
from typing import Any

from app.platform.attachments.image_io import normalize_image_for_llm
from app.platform.doc_retrieval.store import DocRetrievalError, load_figure_bytes

FIGURE_MAX_BYTES = 4 * 1024 * 1024


def read_figure_payload(
    *,
    chat_id,
    attachment_id,
    figure_id: str,
    meta: dict[str, Any],
) -> dict[str, Any]:
    figures = meta.get("figures") or []
    if not isinstance(figures, list):
        raise DocRetrievalError("figure_not_found", f"figure not in meta: {figure_id}")

    figure_meta: dict[str, Any] | None = None
    for fig in figures:
        if isinstance(fig, dict) and str(fig.get("id") or "") == figure_id:
            figure_meta = fig
            break
    if figure_meta is None:
        raise DocRetrievalError("figure_not_found", f"figure not found: {figure_id}")

    filename = str(figure_meta.get("filename") or f"{figure_id}.jpeg")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpeg"
    data = load_figure_bytes(chat_id, attachment_id, figure_id, extension=extension)
    if len(data) > FIGURE_MAX_BYTES:
        raise DocRetrievalError("figure_too_large", f"figure exceeds {FIGURE_MAX_BYTES} bytes")

    normalized, mime_type = normalize_image_for_llm(data)
    encoded = base64.b64encode(normalized).decode("ascii")
    return {
        "figure_id": figure_id,
        "alt": figure_meta.get("alt"),
        "mime_type": mime_type,
        "size_bytes": len(normalized),
        "image_base64": encoded,
        "data_url": f"data:{mime_type};base64,{encoded}",
    }
