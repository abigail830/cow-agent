"""Provider-native attachment upload and MAF content assembly."""

from app.platform.attachments.native.adapters import (
    AnthropicAttachmentAdapter,
    OpenAIAttachmentAdapter,
    get_attachment_upload_adapter,
)
from app.platform.attachments.native.maf_content import (
    attachment_metadata,
    attachment_to_maf_content,
    attachments_to_maf_contents,
    metadata_attachment_to_maf_content,
)
from app.platform.attachments.native.upload import NativeAttachmentUploader

__all__ = [
    "AnthropicAttachmentAdapter",
    "NativeAttachmentUploader",
    "OpenAIAttachmentAdapter",
    "attachment_metadata",
    "attachment_to_maf_content",
    "attachments_to_maf_contents",
    "get_attachment_upload_adapter",
    "metadata_attachment_to_maf_content",
]
