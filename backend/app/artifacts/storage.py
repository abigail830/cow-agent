"""Persist chat-scoped artifacts (slide decks, etc.) — separate from proposal-artifacts."""

from __future__ import annotations

import json
import mimetypes
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.proposal.blob_client import blob_get, blob_put, blob_storage_enabled

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
CHAT_ARTIFACTS_ROOT = _BACKEND_ROOT / "data" / "chat-artifacts"

ChatArtifactFormat = Literal["slidev", "html", "pdf", "markdown"]

_MEDIA_TYPES: dict[str, str] = {
    "slidev": "text/markdown; charset=utf-8",
    "html": "text/html; charset=utf-8",
    "pdf": "application/pdf",
    "markdown": "text/markdown; charset=utf-8",
}


@dataclass(frozen=True)
class ChatArtifactPayload:
    data: bytes
    media_type: str
    filename: str


def new_chat_artifact_id(*, prefix: str = "slide") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _blob_prefix(chat_id: uuid.UUID) -> str:
    return f"chat-artifacts/{chat_id}"


def _blob_object_name(chat_id: uuid.UUID, name: str) -> str:
    return f"{_blob_prefix(chat_id)}/{name}"


def _local_chat_dir(chat_id: uuid.UUID) -> Path:
    return CHAT_ARTIFACTS_ROOT / str(chat_id)


def _meta_path(chat_id: uuid.UUID, artifact_id: str) -> Path:
    return _local_chat_dir(chat_id) / f"{artifact_id}.meta.json"


def _meta_blob_path(chat_id: uuid.UUID, artifact_id: str) -> str:
    return _blob_object_name(chat_id, f"{artifact_id}.meta.json")


def _load_meta(chat_id: uuid.UUID, artifact_id: str) -> dict:
    if blob_storage_enabled():
        raw = blob_get(_meta_blob_path(chat_id, artifact_id))
        if raw:
            try:
                payload = json.loads(raw.decode("utf-8"))
                return payload if isinstance(payload, dict) else {}
            except (UnicodeDecodeError, json.JSONDecodeError):
                return {}
        return {}

    meta_path = _meta_path(chat_id, artifact_id)
    if not meta_path.is_file():
        return {}
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_meta(chat_id: uuid.UUID, artifact_id: str, meta: dict) -> None:
    payload = json.dumps(meta)
    if blob_storage_enabled():
        blob_put(
            _meta_blob_path(chat_id, artifact_id),
            payload,
            content_type="application/json",
        )
        return
    meta_path = _meta_path(chat_id, artifact_id)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(payload, encoding="utf-8")


def _put_bytes(chat_id: uuid.UUID, object_name: str, data: bytes, *, content_type: str) -> None:
    if blob_storage_enabled():
        blob_put(_blob_object_name(chat_id, object_name), data, content_type=content_type)
        return
    path = _local_chat_dir(chat_id) / object_name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _get_bytes(chat_id: uuid.UUID, object_name: str) -> bytes | None:
    if blob_storage_enabled():
        return blob_get(_blob_object_name(chat_id, object_name))
    path = _local_chat_dir(chat_id) / object_name
    if not path.is_file():
        return None
    return path.read_bytes()


def _guess_media_type(path: str, default: str = "application/octet-stream") -> str:
    guessed, _ = mimetypes.guess_type(path)
    return guessed or default


def save_slide_deck(
    chat_id: uuid.UUID,
    artifact_id: str,
    *,
    source_md: str,
    filename: str,
    dist_files: dict[str, bytes] | None = None,
    pdf_bytes: bytes | None = None,
    deck_format: ChatArtifactFormat = "slidev",
) -> None:
    """Persist deck source, built preview assets, and optional PDF."""
    dist_files = dist_files or {}
    source_media = _MEDIA_TYPES.get(deck_format, _MEDIA_TYPES["slidev"])
    source_object = f"{artifact_id}.md" if deck_format == "slidev" else f"{artifact_id}.html"
    _put_bytes(
        chat_id,
        source_object,
        source_md.encode("utf-8"),
        content_type=source_media,
    )

    preview_files: dict[str, str] = {}
    for rel_path, data in dist_files.items():
        rel = rel_path.lstrip("/").replace("\\", "/")
        if not rel or ".." in rel.split("/"):
            continue
        object_name = f"{artifact_id}/dist/{rel}"
        _put_bytes(
            chat_id,
            object_name,
            data,
            content_type=_guess_media_type(rel, "application/octet-stream"),
        )
        preview_files[rel] = object_name

    pdf_object: str | None = None
    if pdf_bytes:
        pdf_object = f"{artifact_id}.pdf"
        _put_bytes(chat_id, pdf_object, pdf_bytes, content_type=_MEDIA_TYPES["pdf"])

    meta = {
        "kind": "slide_deck",
        "filename": filename,
        "format": deck_format,
        "media_type": source_media,
        "source_object": source_object,
        "preview_index": "index.html" if "index.html" in preview_files else None,
        "preview_files": preview_files,
        "variants": {},
    }
    if pdf_object:
        meta["variants"]["pdf"] = {
            "filename": filename.replace(".md", ".pdf") if filename.endswith(".md") else f"{filename}.pdf",
            "format": "pdf",
            "media_type": _MEDIA_TYPES["pdf"],
            "object_name": pdf_object,
        }
    _write_meta(chat_id, artifact_id, meta)


def chat_artifact_exists(chat_id: uuid.UUID, artifact_id: str) -> bool:
    if not artifact_id or ".." in artifact_id or "/" in artifact_id:
        return False
    meta = _load_meta(chat_id, artifact_id)
    return bool(meta)


def get_chat_artifact_format(chat_id: uuid.UUID, artifact_id: str) -> str:
    meta = _load_meta(chat_id, artifact_id)
    fmt = str(meta.get("format") or "slidev").strip().lower()
    return fmt if fmt in {"slidev", "html", "pdf", "markdown"} else "slidev"


def load_chat_artifact_payload(
    chat_id: uuid.UUID,
    artifact_id: str,
    *,
    variant: str | None = None,
) -> ChatArtifactPayload | None:
    if not chat_artifact_exists(chat_id, artifact_id):
        return None

    meta = _load_meta(chat_id, artifact_id)
    if variant:
        variants = meta.get("variants")
        if not isinstance(variants, dict):
            return None
        entry = variants.get(variant)
        if not isinstance(entry, dict):
            return None
        object_name = str(entry.get("object_name") or "").strip()
        if not object_name:
            return None
        raw = _get_bytes(chat_id, object_name)
        if raw is None:
            return None
        return ChatArtifactPayload(
            data=raw,
            media_type=str(entry.get("media_type") or _MEDIA_TYPES["pdf"]),
            filename=str(entry.get("filename") or f"{artifact_id}.{variant}"),
        )

    source_object = str(meta.get("source_object") or f"{artifact_id}.md")
    raw = _get_bytes(chat_id, source_object)
    if raw is None:
        return None
    return ChatArtifactPayload(
        data=raw,
        media_type=str(meta.get("media_type") or _MEDIA_TYPES["slidev"]),
        filename=str(meta.get("filename") or f"{artifact_id}.md"),
    )


def load_slide_preview_payload(
    chat_id: uuid.UUID,
    artifact_id: str,
    file_path: str,
) -> ChatArtifactPayload | None:
    if not chat_artifact_exists(chat_id, artifact_id):
        return None

    rel = file_path.lstrip("/").replace("\\", "/")
    if not rel:
        meta = _load_meta(chat_id, artifact_id)
        rel = str(meta.get("preview_index") or "index.html").lstrip("/")
    if not rel or ".." in rel.split("/"):
        return None

    meta = _load_meta(chat_id, artifact_id)
    preview_files = meta.get("preview_files")
    object_name: str | None = None
    if isinstance(preview_files, dict):
        object_name = preview_files.get(rel)
    if not object_name:
        object_name = f"{artifact_id}/dist/{rel}"

    raw = _get_bytes(chat_id, object_name)
    if raw is None:
        return None
    return ChatArtifactPayload(
        data=raw,
        media_type=_guess_media_type(rel, "application/octet-stream"),
        filename=Path(rel).name,
    )
