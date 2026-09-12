"""Chat attachment processing — native (provider) and unify-lite (platform) paths."""

from app.platform.attachments.modes import AttachmentProcessingMode, DEFAULT_ATTACHMENT_MODE, parse_attachment_mode
from app.platform.attachments.service import AttachmentService

__all__ = [
    "AttachmentProcessingMode",
    "AttachmentService",
    "DEFAULT_ATTACHMENT_MODE",
    "parse_attachment_mode",
]
