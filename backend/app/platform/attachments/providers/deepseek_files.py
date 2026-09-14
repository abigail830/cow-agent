"""DeepSeek Files API — upload images for chat `file_id` references."""

from __future__ import annotations

import logging

import httpx

from app.config import Settings, get_settings
from app.platform.attachments.providers.adapters import UploadedProviderFile
from app.platform.llm.model_registry import ModelProvider

logger = logging.getLogger(__name__)

_DEEPSEEK_IMAGE_MIMES = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})


class DeepSeekAttachmentAdapter:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def upload(self, *, filename: str, mime_type: str, data: bytes) -> UploadedProviderFile:
        api_key = self._settings.deepseek_api_key
        if not api_key:
            raise ValueError("DeepSeek is not configured (DEEPSEEK_API_KEY)")
        normalized = (mime_type or "application/octet-stream").split(";", 1)[0].strip().lower()
        if normalized not in _DEEPSEEK_IMAGE_MIMES:
            raise ValueError(
                "DeepSeek Files API accepts JPEG/PNG/GIF/WebP images only. "
                "Convert PDFs on the platform before upload."
            )
        base = self._settings.deepseek_base_url.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        url = f"{base}/files"
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (filename, data, mime_type)},
                data={"purpose": "user_data"},
            )
        if response.status_code >= 400:
            logger.warning("DeepSeek file upload failed: %s %s", response.status_code, response.text[:500])
            detail = response.text.strip()
            try:
                payload = response.json()
                message = (payload.get("error") or {}).get("message")
                if message:
                    detail = str(message)
            except (ValueError, TypeError, AttributeError):
                pass
            raise RuntimeError(f"DeepSeek file upload failed ({response.status_code}): {detail}") from None
        payload = response.json()
        file_id = payload.get("id")
        if not file_id:
            raise RuntimeError("DeepSeek Files API did not return file id")
        return UploadedProviderFile(
            provider=ModelProvider.DEEPSEEK.value,
            provider_file_id=str(file_id),
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
        )
