import pytest

from app.platform.attachment_adapters import validate_attachment_file, validate_message_attachments


def test_validate_attachment_file_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        validate_attachment_file(filename="a.txt", mime_type="text/plain", size_bytes=0)


def test_validate_attachment_file_rejects_oversized():
    with pytest.raises(ValueError, match="limit"):
        validate_attachment_file(
            filename="big.pdf",
            mime_type="application/pdf",
            size_bytes=50 * 1024 * 1024 + 1,
        )


def test_validate_attachment_file_rejects_unsupported_type():
    with pytest.raises(ValueError, match="Unsupported"):
        validate_attachment_file(
            filename="archive.zip",
            mime_type="application/zip",
            size_bytes=100,
        )


def test_validate_attachment_file_accepts_pdf():
    validate_attachment_file(filename="doc.pdf", mime_type="application/pdf", size_bytes=1024)


def test_validate_message_attachments_rejects_too_many():
    sizes = [1024] * 6
    with pytest.raises(ValueError, match="At most"):
        validate_message_attachments(size_bytes_list=sizes)


def test_validate_message_attachments_rejects_total_size():
    half = 50 * 1024 * 1024 // 2 + 1
    with pytest.raises(ValueError, match="Combined"):
        validate_message_attachments(size_bytes_list=[half, half])


def test_validate_message_attachments_accepts_within_limits():
    validate_message_attachments(size_bytes_list=[1024, 2048, 4096])
