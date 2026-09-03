import uuid

from agent_framework import Content

from app.platform.attachment_adapters import (
    attachment_to_maf_content,
    metadata_attachment_to_maf_content,
    should_use_azure_inline_image,
)
from app.platform.attachment_storage import (
    format_inline_provider_file_id,
    is_inline_provider_file_id,
    save_inline_attachment,
)


def test_should_use_azure_inline_image_for_png():
    assert should_use_azure_inline_image(
        base_url="https://example.cognitiveservices.azure.com/openai",
        mime_type="image/png",
    )
    assert not should_use_azure_inline_image(
        base_url="https://api.openai.com/v1",
        mime_type="image/png",
    )


def test_inline_provider_file_id_roundtrip():
    attachment_id = uuid.uuid4()
    provider_file_id = format_inline_provider_file_id(attachment_id)
    assert is_inline_provider_file_id(provider_file_id)


class _InlineAttachment:
    def __init__(self, chat_id: uuid.UUID, attachment_id: uuid.UUID) -> None:
        self.chat_id = chat_id
        self.provider_file_id = format_inline_provider_file_id(attachment_id)
        self.mime_type = "image/png"
        self.filename = "screenshot.png"


def test_attachment_to_maf_content_inline_image(tmp_path, monkeypatch):
    from app.platform import attachment_storage

    monkeypatch.setattr(attachment_storage, "INLINE_ATTACHMENTS_ROOT", tmp_path)

    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    save_inline_attachment(chat_id, attachment_id, b"\x89PNG\r\n\x1a\n")

    content = attachment_to_maf_content(_InlineAttachment(chat_id, attachment_id))
    assert isinstance(content, Content)
    assert content.type == "data"
    assert content.media_type == "image/png"


def test_metadata_attachment_to_maf_content_inline_image(tmp_path, monkeypatch):
    from app.platform import attachment_storage

    monkeypatch.setattr(attachment_storage, "INLINE_ATTACHMENTS_ROOT", tmp_path)

    chat_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    save_inline_attachment(chat_id, attachment_id, b"\x89PNG\r\n\x1a\n")

    item = {
        "id": str(attachment_id),
        "filename": "screenshot.png",
        "mime_type": "image/png",
        "provider_file_id": format_inline_provider_file_id(attachment_id),
    }
    content = metadata_attachment_to_maf_content(item, chat_id=chat_id)
    assert content is not None
    assert content.type == "data"
