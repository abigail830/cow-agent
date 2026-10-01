"""Upload chat attachments to provider Files APIs (DeepSeek only; domestic chat models use inline / file_data / hydrate)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from app.config import Settings, get_settings
from app.platform.llm.model_registry import ModelProvider

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadedProviderFile:
    provider: str
    provider_file_id: str
    filename: str
    mime_type: str
    size_bytes: int


class AttachmentUploadAdapter(Protocol):
    async def upload(self, *, filename: str, mime_type: str, data: bytes) -> UploadedProviderFile: ...


def get_attachment_upload_adapter(provider: str, settings: Settings | None = None) -> AttachmentUploadAdapter:
    if provider == ModelProvider.DEEPSEEK.value:
        from app.platform.attachments.providers.deepseek_files import DeepSeekAttachmentAdapter

        return DeepSeekAttachmentAdapter(settings)
    raise ValueError(
        f"Unsupported model provider for provider Files API uploads: {provider}. "
        "Use inline images, Qwen file_data PDFs, or parse hydrate for documents."
    )
