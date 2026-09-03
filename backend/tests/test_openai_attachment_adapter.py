import pytest

from app.platform.attachment_adapters import (
    _azure_openai_files_url,
    azure_openai_file_upload_purpose,
    is_azure_openai_base_url,
    validate_azure_openai_attachment_mime,
)


def test_is_azure_openai_base_url():
    assert is_azure_openai_base_url("https://smart-sales.cognitiveservices.azure.com/openai")
    assert is_azure_openai_base_url("https://my-resource.openai.azure.com/")
    assert not is_azure_openai_base_url("https://api.openai.com/v1")


def test_azure_openai_files_url_uses_v1_path():
    url = _azure_openai_files_url(
        "https://smart-sales.cognitiveservices.azure.com/openai",
        "preview",
    )
    assert url == (
        "https://smart-sales.cognitiveservices.azure.com/openai/v1/files?api-version=preview"
    )


def test_azure_openai_file_upload_purpose():
    assert azure_openai_file_upload_purpose("https://example.cognitiveservices.azure.com/openai") == "assistants"
    assert azure_openai_file_upload_purpose("https://api.openai.com/v1") == "user_data"


def test_validate_azure_openai_attachment_mime_accepts_pdf():
    validate_azure_openai_attachment_mime(
        base_url="https://example.cognitiveservices.azure.com/openai",
        mime_type="application/pdf",
        filename="proposal.pdf",
    )


def test_validate_azure_openai_attachment_mime_accepts_png():
    validate_azure_openai_attachment_mime(
        base_url="https://example.cognitiveservices.azure.com/openai",
        mime_type="image/png",
        filename="screenshot.png",
    )


def test_validate_azure_openai_attachment_mime_rejects_docx():
    with pytest.raises(ValueError, match="PDF file attachments"):
        validate_azure_openai_attachment_mime(
            base_url="https://example.cognitiveservices.azure.com/openai",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="proposal.docx",
        )


def test_validate_azure_openai_attachment_mime_ignored_for_openai():
    validate_azure_openai_attachment_mime(
        base_url="https://api.openai.com/v1",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="proposal.docx",
    )
