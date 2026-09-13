"""Map one attachment to a durable text summary (explicit map_attachment)."""

from __future__ import annotations

import hashlib
from typing import Any

from app.config import Settings, get_settings
from app.platform.attachments.attachment_storage import load_inline_attachment, parse_inline_attachment_id
from app.platform.attachments.run_state import get_attachment_run_state
from app.platform.attachments.services.ephemeral import ephemeral_text_run
from app.platform.attachments.services.read import AttachmentReadService
from app.platform.attachments.services.vision import (
    ATTACHMENT_VISION_WORKER_INSTRUCTIONS,
    AttachmentVisionService,
    get_attachment_vision_service,
)
from app.platform.attachments.unify_lite.validation import is_unify_lite_image

ATTACHMENT_MAP_WORKER_INSTRUCTIONS = (
    "You are an attachment summarization worker for a chat platform.\n"
    "Produce a concise summary for another assistant that cannot read the full file.\n"
    "Preserve key facts, numbers, headings, and structure when present.\n"
    "Reply with plain text only — no markdown code fences."
)

_MAP_EXTRACT_MAX_CHARS = 32_000


def map_cache_key(attachment_id: str, content_hash: str | None, focus: str | None) -> str:
    focus_digest = hashlib.sha256((focus or "").strip().lower().encode("utf-8")).hexdigest()[:16]
    return f"{attachment_id}:{content_hash or ''}:{focus_digest}"


class AttachmentMapService:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        vision_service: AttachmentVisionService | None = None,
        read_service: AttachmentReadService | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._vision = vision_service or get_attachment_vision_service()
        self._read = read_service or AttachmentReadService(self._settings)

    async def map_one(
        self,
        attachment_id: str,
        focus: str | None = None,
    ) -> dict[str, Any]:
        state = get_attachment_run_state()
        if state is None:
            return {"status": "error", "message": "Attachment context is not initialized for this run."}

        record = state.attachments.get(attachment_id)
        if record is None:
            return {"status": "error", "message": "Attachment not found in this chat."}
        if str(record.chat_id) != str(state.chat_id):
            return {"status": "error", "message": "Attachment does not belong to this chat."}

        content_hash = record.content_hash
        cache_key = map_cache_key(attachment_id, content_hash, focus)
        cached = state.map_cache.get(cache_key)
        if cached is not None:
            return {**cached, "cached": True}

        try:
            blob_id = parse_inline_attachment_id(record.provider_file_id)
            data = load_inline_attachment(record.chat_id, blob_id)
        except (OSError, ValueError) as exc:
            return {
                "status": "error",
                "message": str(exc),
                "confidence": "failed",
                "attachment_id": attachment_id,
            }

        state.page_in_ids.add(attachment_id)

        if is_unify_lite_image(filename=record.filename, mime_type=record.mime_type):
            question = focus or "Summarize this image for a chat assistant."
            vision = await self._vision.describe(
                data=data,
                mime_type=record.mime_type,
                filename=record.filename,
                question=question,
            )
            if vision.get("status") != "ok":
                return {
                    "status": "error",
                    "message": str(vision.get("message") or "Vision map failed."),
                    "confidence": "failed",
                    "attachment_id": attachment_id,
                    "filename": record.filename,
                }
            payload: dict[str, Any] = {
                "status": "ok",
                "attachment_id": attachment_id,
                "filename": record.filename,
                "summary": vision.get("summary"),
                "confidence": vision.get("confidence", "ok"),
                "full_available": True,
            }
        else:
            try:
                text, warnings, truncated = self._read.extract_text(
                    filename=record.filename,
                    mime_type=record.mime_type,
                    data=data,
                    max_chars=_MAP_EXTRACT_MAX_CHARS,
                )
            except ValueError as exc:
                return {
                    "status": "error",
                    "message": str(exc),
                    "confidence": "failed",
                    "attachment_id": attachment_id,
                    "filename": record.filename,
                }

            focus_line = f"Focus: {focus.strip()}\n\n" if focus and focus.strip() else ""
            prompt = (
                f"Filename: {record.filename}\n\n"
                f"{focus_line}"
                f"---\n{text}\n---\n\n"
                "Write a concise summary for the chat assistant."
            )
            try:
                summary = await ephemeral_text_run(
                    instructions=ATTACHMENT_MAP_WORKER_INSTRUCTIONS,
                    prompt=prompt,
                    settings=self._settings,
                )
            except Exception as exc:  # noqa: BLE001
                return {
                    "status": "error",
                    "message": f"Map summarization failed: {exc}",
                    "confidence": "failed",
                    "attachment_id": attachment_id,
                    "filename": record.filename,
                }
            if not summary:
                return {
                    "status": "error",
                    "message": "Map worker returned an empty summary.",
                    "confidence": "failed",
                    "attachment_id": attachment_id,
                    "filename": record.filename,
                }
            payload = {
                "status": "ok",
                "attachment_id": attachment_id,
                "filename": record.filename,
                "summary": summary,
                "confidence": "ok",
                "full_available": True,
            }
            if warnings:
                payload["warnings"] = warnings[:5]
            if truncated:
                payload["truncated_source"] = True

        if content_hash:
            payload["content_hash"] = content_hash
        state.map_cache[cache_key] = payload
        return payload


_map_service: AttachmentMapService | None = None


def get_attachment_map_service() -> AttachmentMapService:
    global _map_service
    if _map_service is None:
        _map_service = AttachmentMapService()
    return _map_service
