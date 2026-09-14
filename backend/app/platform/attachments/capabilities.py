"""Attachment routing capabilities — looked up by model id / provider, never probed at runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.platform.llm.model_registry import ModelProvider

ImageTransport = Literal["file_id", "inline"]
PdfTransport = Literal["file_id", "file_data", "raster"]


@dataclass(frozen=True)
class AttachmentCapabilities:
    image_via: ImageTransport
    pdf_via: PdfTransport

    @property
    def accepts_pdf(self) -> bool:
        return self.pdf_via in {"file_id", "file_data"}

    @property
    def image_file_id(self) -> bool:
        return self.image_via == "file_id"

    @property
    def pdf_file_id(self) -> bool:
        return self.pdf_via == "file_id"


_BY_MODEL_ID: dict[str, AttachmentCapabilities] = {
    "gpt-5.4": AttachmentCapabilities(image_via="inline", pdf_via="file_id"),
    "claude-sonnet-4-6": AttachmentCapabilities(image_via="file_id", pdf_via="file_id"),
    "qwen3.7-plus": AttachmentCapabilities(image_via="inline", pdf_via="file_data"),
    "qwen3.8-max": AttachmentCapabilities(image_via="inline", pdf_via="file_data"),
    "minimax-m3": AttachmentCapabilities(image_via="inline", pdf_via="raster"),
    "deepseek-flash": AttachmentCapabilities(image_via="file_id", pdf_via="raster"),
}

_BY_PROVIDER: dict[str, AttachmentCapabilities] = {
    ModelProvider.AZURE_OPENAI.value: AttachmentCapabilities(image_via="inline", pdf_via="file_id"),
    ModelProvider.AZURE_ANTHROPIC.value: AttachmentCapabilities(image_via="file_id", pdf_via="file_id"),
    ModelProvider.DASHSCOPE.value: AttachmentCapabilities(image_via="inline", pdf_via="file_data"),
    ModelProvider.DEEPSEEK.value: AttachmentCapabilities(image_via="file_id", pdf_via="raster"),
    ModelProvider.SILICONFLOW.value: AttachmentCapabilities(image_via="inline", pdf_via="raster"),
}

_DEFAULT = AttachmentCapabilities(image_via="inline", pdf_via="raster")


def attachment_capabilities(*, model_id: str | None = None, provider: str | None = None) -> AttachmentCapabilities:
    """Resolve routing for the current chat model. Model id wins over provider."""
    if model_id:
        key = str(model_id).strip().lower()
        if key in _BY_MODEL_ID:
            return _BY_MODEL_ID[key]
        if key.startswith("minimax"):
            return _BY_MODEL_ID["minimax-m3"]
        if key.startswith("qwen"):
            return _BY_MODEL_ID["qwen3.8-max"]
        if key.startswith("deepseek"):
            return _BY_MODEL_ID["deepseek-flash"]
        if key.startswith("claude"):
            return _BY_MODEL_ID["claude-sonnet-4-6"]
        if key.startswith("gpt"):
            return _BY_MODEL_ID["gpt-5.4"]
    if provider:
        found = _BY_PROVIDER.get(str(provider).strip().lower())
        if found is not None:
            return found
    return _DEFAULT
