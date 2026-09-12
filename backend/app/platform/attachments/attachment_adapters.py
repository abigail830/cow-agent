"""Backward-compatible re-exports — prefer ``native`` / ``validation`` submodules."""

from __future__ import annotations

from app.platform.attachments.native.adapters import (
    AnthropicAttachmentAdapter,
    OpenAIAttachmentAdapter,
    UploadedProviderFile,
    azure_openai_file_upload_purpose,
    get_attachment_upload_adapter,
    is_azure_openai_base_url,
    should_use_azure_inline_image,
    validate_azure_openai_attachment_mime,
)
from app.platform.attachments.native.maf_content import (
    attachment_metadata,
    attachment_to_maf_content,
    attachments_to_maf_contents,
    metadata_attachment_to_maf_content,
)
from app.platform.attachments.validation import (
    ALLOWED_MIME_TYPES,
    SUPPORTED_ATTACHMENT_EXTENSIONS,
    validate_attachment_file,
    validate_message_attachments,
)

__all__ = [
    "ALLOWED_MIME_TYPES",
    "AnthropicAttachmentAdapter",
    "OpenAIAttachmentAdapter",
    "SUPPORTED_ATTACHMENT_EXTENSIONS",
    "UploadedProviderFile",
    "attachment_metadata",
    "attachment_to_maf_content",
    "attachments_to_maf_contents",
    "azure_openai_file_upload_purpose",
    "get_attachment_upload_adapter",
    "is_azure_openai_base_url",
    "metadata_attachment_to_maf_content",
    "should_use_azure_inline_image",
    "validate_attachment_file",
    "validate_azure_openai_attachment_mime",
    "validate_message_attachments",
]
