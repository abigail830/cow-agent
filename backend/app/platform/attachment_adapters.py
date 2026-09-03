"""Upload chat attachments directly to each LLM provider's Files API."""

from __future__ import annotations

import io
import logging
import uuid
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode, urlparse, urlunparse

import httpx
from agent_framework import Content

from app.config import Settings, get_settings
from app.platform.attachment_limits import attachment_limits
from app.platform.attachment_storage import (
    is_image_mime,
    is_inline_provider_file_id,
    load_inline_attachment,
    parse_inline_attachment_id,
)
from app.platform.model_registry import ModelProvider

logger = logging.getLogger(__name__)

# Azure Responses API currently accepts PDF file_id inputs only (not docx/xlsx).
AZURE_OPENAI_FILE_INPUT_MIME_TYPES = frozenset({"application/pdf"})

ALLOWED_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "text/plain",
        "text/csv",
        "text/markdown",
        "application/json",
        "image/jpeg",
        "image/png",
        "image/gif",
        "image/webp",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/msword",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
    }
)


# Human-readable summary for API errors / docs
SUPPORTED_ATTACHMENT_EXTENSIONS = (
    ".pdf",
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
)


@dataclass(frozen=True)
class UploadedProviderFile:
    provider: str
    provider_file_id: str
    filename: str
    mime_type: str
    size_bytes: int


class AttachmentUploadAdapter(Protocol):
    async def upload(self, *, filename: str, mime_type: str, data: bytes) -> UploadedProviderFile: ...


def validate_attachment_file(
    *,
    filename: str,
    mime_type: str,
    size_bytes: int,
    settings: Settings | None = None,
) -> None:
    _, max_file_bytes, _ = attachment_limits(settings)
    if size_bytes <= 0:
        raise ValueError("File is empty")
    if size_bytes > max_file_bytes:
        raise ValueError(f"File exceeds {max_file_bytes // (1024 * 1024)} MB limit")
    normalized = (mime_type or "application/octet-stream").split(";", 1)[0].strip().lower()
    if normalized not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Unsupported file type: {normalized or filename}")


def validate_message_attachments(*, size_bytes_list: list[int], settings: Settings | None = None) -> None:
    """Enforce platform-wide per-message limits (same for all providers)."""
    max_files, _, max_total_bytes = attachment_limits(settings)
    count = len(size_bytes_list)
    if count > max_files:
        raise ValueError(f"At most {max_files} attachments per message")
    total = sum(size_bytes_list)
    if total > max_total_bytes:
        limit_mb = max_total_bytes // (1024 * 1024)
        raise ValueError(f"Combined attachment size exceeds {limit_mb} MB per message")


def is_azure_openai_base_url(base_url: str) -> bool:
    host = urlparse(base_url).netloc.lower()
    return host.endswith(".openai.azure.com") or host.endswith(".cognitiveservices.azure.com")


def azure_openai_file_upload_purpose(base_url: str) -> str:
    # Azure rejects user_data today; assistants returns assistant-* ids for Responses input_file.
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


def attachment_to_maf_content(att) -> Content:
    provider_file_id = str(getattr(att, "provider_file_id", "") or "")
    mime_type = str(getattr(att, "mime_type", "") or "application/octet-stream")
    filename = str(getattr(att, "filename", "") or "attachment")

    if is_inline_provider_file_id(provider_file_id):
        chat_id = getattr(att, "chat_id", None)
        if chat_id is None:
            raise ValueError("Inline attachment is missing chat_id")
        attachment_id = parse_inline_attachment_id(provider_file_id)
        data = load_inline_attachment(chat_id, attachment_id)
        return Content.from_data(
            data=data,
            media_type=mime_type,
            additional_properties={"filename": filename},
        )

    return Content.from_hosted_file(
        file_id=provider_file_id,
        media_type=mime_type,
        name=filename,
    )


def metadata_attachment_to_maf_content(item: dict, *, chat_id: uuid.UUID) -> Content | None:
    file_id = item.get("provider_file_id")
    if not file_id:
        return None
    mime_type = str(item.get("mime_type") or "application/octet-stream")
    filename = str(item.get("filename") or "attachment")
    if is_inline_provider_file_id(str(file_id)):
        attachment_id = uuid.UUID(str(item.get("id") or parse_inline_attachment_id(str(file_id))))
        data = load_inline_attachment(chat_id, attachment_id)
        return Content.from_data(
            data=data,
            media_type=mime_type,
            additional_properties={"filename": filename},
        )
    return Content.from_hosted_file(
        file_id=str(file_id),
        media_type=mime_type,
        name=filename,
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


def attachments_to_maf_contents(attachments: list) -> list[Content]:
    return [attachment_to_maf_content(att) for att in attachments]


def attachment_metadata(att) -> dict:
    return {
        "id": str(att.id),
        "filename": att.filename,
        "mime_type": att.mime_type,
        "size_bytes": att.size_bytes,
        "provider": att.provider,
        "provider_file_id": att.provider_file_id,
    }
