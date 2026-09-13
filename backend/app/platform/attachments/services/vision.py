"""Isolated vision analysis for chat image attachments."""

from __future__ import annotations

from agent_framework import Content, Message

from app.config import Settings, get_settings
from app.platform.attachments.services.ephemeral import ephemeral_vision_run, resolve_vision_model_entry
from app.platform.attachments.services.vision_resize import resize_image_for_vision

# Stable prefix for worker mini-requests (Auto prefix cache on domestic providers).
ATTACHMENT_VISION_WORKER_INSTRUCTIONS = (
    "You are an attachment vision analysis worker for a chat platform.\n"
    "Describe the image accurately and concisely for another assistant that cannot see pixels.\n"
    "Include visible text, labels, chart values, colors, and layout when relevant.\n"
    "Reply with plain text only — no markdown code fences."
)


class AttachmentVisionService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def describe(
        self,
        *,
        data: bytes,
        mime_type: str,
        filename: str,
        question: str | None = None,
    ) -> dict[str, object]:
        if not self._settings.attachment_vision_service_enabled:
            return {
                "status": "error",
                "message": (
                    "Attachment vision service is disabled. "
                    "Set ATTACHMENT_VISION_SERVICE_ENABLED=true to analyze images."
                ),
            }

        resized = resize_image_for_vision(
            data,
            mime_type=mime_type,
            max_edge=self._settings.attachment_vision_max_edge,
            jpeg_quality=self._settings.attachment_vision_jpeg_quality,
        )
        focus = (question or "").strip() or "Describe this image in detail for a chat assistant."
        user_message = Message(
            role="user",
            contents=[
                Content.from_text(f"Filename: {filename}\n\n{focus}"),
                Content.from_data(
                    data=resized.data,
                    media_type=resized.media_type,
                    additional_properties={"filename": filename},
                ),
            ],
        )
        try:
            model_entry = resolve_vision_model_entry(settings=self._settings)
            summary = await ephemeral_vision_run(
                instructions=ATTACHMENT_VISION_WORKER_INSTRUCTIONS,
                user_message=user_message,
                model_id=model_entry.id,
                settings=self._settings,
            )
        except Exception as exc:  # noqa: BLE001 — surface as tool failure
            return {
                "status": "error",
                "message": f"Vision analysis failed: {exc}",
                "confidence": "failed",
            }

        if not summary:
            return {
                "status": "error",
                "message": "Vision model returned an empty description.",
                "confidence": "failed",
            }

        payload: dict[str, object] = {
            "status": "ok",
            "summary": summary,
            "confidence": "ok",
            "full_available": True,
            "media_type": resized.media_type,
            "size_bytes": len(resized.data),
        }
        if resized.resized:
            payload["vision_resized"] = True
            payload["vision_width"] = resized.width
            payload["vision_height"] = resized.height
        if question:
            payload["question"] = question
        return payload


_vision_service: AttachmentVisionService | None = None


def get_attachment_vision_service() -> AttachmentVisionService:
    global _vision_service
    if _vision_service is None:
        _vision_service = AttachmentVisionService()
    return _vision_service
