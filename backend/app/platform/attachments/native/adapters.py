"""Upload chat attachments to each LLM provider's Files API."""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode, urlparse, urlunparse

import httpx

from app.config import Settings, get_settings
from app.platform.attachments.attachment_storage import is_image_mime
from app.platform.attachments.validation import ALLOWED_MIME_TYPES  # noqa: F401 — re-exported
from app.platform.llm.model_registry import ModelProvider

logger = logging.getLogger(__name__)

# Azure Responses API currently accepts PDF file_id inputs only (not docx/xlsx).
AZURE_OPENAI_FILE_INPUT_MIME_TYPES = frozenset({"application/pdf"})


@dataclass(frozen=True)
class UploadedProviderFile:
    provider: str
    provider_file_id: str
    filename: str
    mime_type: str
    size_bytes: int


class AttachmentUploadAdapter(Protocol):
    async def upload(self, *, filename: str, mime_type: str, data: bytes) -> UploadedProviderFile: ...


def is_azure_openai_base_url(base_url: str) -> bool:
    host = urlparse(base_url).netloc.lower()
    return host.endswith(".openai.azure.com") or host.endswith(".cognitiveservices.azure.com")


def azure_openai_file_upload_purpose(base_url: str) -> str:
    return "assistants" if is_azure_openai_base_url(base_url) else "user_data"


def should_use_azure_inline_image(*, base_url: str, mime_type: str) -> bool:
    """Azure Responses file_id inputs are PDF-only; images use inline vision data."""
    return is_azure_openai_base_url(base_url) and is_image_mime(mime_type)


def validate_azure_openai_attachment_mime(*, base_url: str, mime_type: str, filename: str) -> None:
    if not is_azure_openai_base_url(base_url):
        return
    if should_use_azure_inline_image(base_url=base_url, mime_type=mime_type):
        return
    normalized = (mime_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    if normalized in AZURE_OPENAI_FILE_INPUT_MIME_TYPES:
        return
    if filename.lower().endswith(".pdf"):
        return
    raise ValueError(
        "Azure OpenAI currently supports PDF file attachments and pasted/screenshot images. "
        "Convert Word/Excel files to PDF, or paste the text into your message."
    )


def _azure_openai_files_url(base_url: str, api_version: str) -> str:
    parsed = urlparse(base_url.rstrip("/"))
    path = parsed.path.rstrip("/")
    if path.endswith("/openai/v1"):
        path = f"{path}/files"
    elif path.endswith("/openai"):
        path = f"{path}/v1/files"
    elif path.endswith("/v1"):
        path = f"{path}/files"
    else:
        path = f"{path}/openai/v1/files" if "/openai" not in path else f"{path}/files"
    query = urlencode({"api-version": api_version})
    return urlunparse(parsed._replace(path=path, query=query))


class OpenAIAttachmentAdapter:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def upload(self, *, filename: str, mime_type: str, data: bytes) -> UploadedProviderFile:
        base_url = self._settings.azure_openai_base_url
        validate_azure_openai_attachment_mime(base_url=base_url, mime_type=mime_type, filename=filename)
        files_api_version = (
            self._settings.azure_openai_files_api_version
            if is_azure_openai_base_url(base_url)
            else self._settings.azure_openai_api_version
        )
        purpose = azure_openai_file_upload_purpose(base_url)
        url = _azure_openai_files_url(base_url, files_api_version)
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                url,
                headers={"api-key": self._settings.azure_api_key},
                files={"file": (filename, data, mime_type)},
                data={"purpose": purpose},
            )
        if response.status_code >= 400:
            logger.warning("OpenAI file upload failed: %s %s", response.status_code, response.text[:500])
            detail = response.text.strip()
            try:
                payload = response.json()
                message = (payload.get("error") or {}).get("message")
                if message:
                    detail = str(message)
            except (ValueError, TypeError, AttributeError):
                pass
            raise RuntimeError(f"OpenAI file upload failed ({response.status_code}): {detail}") from None
        payload = response.json()
        file_id = payload.get("id")
        if not file_id:
            raise RuntimeError("OpenAI Files API did not return file id")
        return UploadedProviderFile(
            provider=ModelProvider.AZURE_OPENAI.value,
            provider_file_id=str(file_id),
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
        )


class AnthropicAttachmentAdapter:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def upload(self, *, filename: str, mime_type: str, data: bytes) -> UploadedProviderFile:
        from anthropic import AsyncAnthropic

        api_key = self._settings.claude_azure_api_key
        base_url = self._settings.claude_azure_foundry_endpoint
        if not api_key or not base_url:
            raise ValueError("Claude is not configured (CLAUDE_AZURE_* env vars)")

        client = AsyncAnthropic(api_key=api_key, base_url=base_url.rstrip("/"))
        uploaded = await client.beta.files.upload(
            file=(filename, io.BytesIO(data), mime_type),
        )
        return UploadedProviderFile(
            provider=ModelProvider.AZURE_ANTHROPIC.value,
            provider_file_id=str(uploaded.id),
            filename=filename,
            mime_type=mime_type,
            size_bytes=len(data),
        )


def get_attachment_upload_adapter(provider: str, settings: Settings | None = None) -> AttachmentUploadAdapter:
    if provider == ModelProvider.AZURE_OPENAI.value:
        return OpenAIAttachmentAdapter(settings)
    if provider == ModelProvider.AZURE_ANTHROPIC.value:
        return AnthropicAttachmentAdapter(settings)
    raise ValueError(f"Unsupported model provider for attachments: {provider}")


# Re-export for tests that import ALLOWED_MIME_TYPES from adapters historically.
__all__ = [
    "ALLOWED_MIME_TYPES",
    "AnthropicAttachmentAdapter",
    "AttachmentUploadAdapter",
    "OpenAIAttachmentAdapter",
    "UploadedProviderFile",
    "azure_openai_file_upload_purpose",
    "get_attachment_upload_adapter",
    "is_azure_openai_base_url",
    "should_use_azure_inline_image",
    "validate_azure_openai_attachment_mime",
]
