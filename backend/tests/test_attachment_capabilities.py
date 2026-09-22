from app.platform.attachments.capabilities import attachment_capabilities
from app.platform.attachments.kinds import (
    AttachmentKind,
    OFFICE_REJECT_PPT,
    OFFICE_REJECT_WORD,
    classify_attachment,
    office_reject_message,
    page_cost_for_kind,
)
from app.platform.attachments.validation import validate_attachment_file, validate_message_attachments
import pytest


def test_capabilities_by_model_id():
    assert attachment_capabilities(model_id="gpt-5.4").pdf_via == "file_id"
    assert attachment_capabilities(model_id="gpt-5.4").image_via == "inline"
    assert attachment_capabilities(model_id="claude-sonnet-4-6").image_via == "file_id"
    assert attachment_capabilities(model_id="qwen3.8-max").pdf_via == "file_data"
    assert attachment_capabilities(model_id="minimax-m3").pdf_via == "raster"
    assert attachment_capabilities(model_id="deepseek-flash").image_via == "inline"
    assert attachment_capabilities(model_id="deepseek-flash").pdf_via == "raster"


def test_capabilities_prefix_fallback():
    assert attachment_capabilities(model_id="qwen3.7-plus").accepts_pdf is True
    assert attachment_capabilities(model_id="MiniMax/MiniMax-M3").pdf_via == "raster"
    assert attachment_capabilities(model_id="deepseek-chat").image_file_id is False


def test_classify_and_office_reject():
    assert classify_attachment(filename="a.png", mime_type="image/png") == AttachmentKind.IMAGE
    assert classify_attachment(filename="a.pdf", mime_type="application/pdf") == AttachmentKind.PDF
    assert classify_attachment(filename="a.xlsx", mime_type="") == AttachmentKind.SHEET
    assert classify_attachment(filename="notes.md", mime_type="text/markdown") == AttachmentKind.TEXT
    assert classify_attachment(filename="deck.pptx", mime_type="") == AttachmentKind.OFFICE
    assert office_reject_message(filename="deck.pptx", mime_type="") == OFFICE_REJECT_PPT
    assert office_reject_message(filename="doc.docx", mime_type="") == OFFICE_REJECT_WORD


def test_validate_rejects_ppt_and_word():
    with pytest.raises(ValueError, match="PowerPoint"):
        validate_attachment_file(filename="deck.pptx", mime_type="", size_bytes=100)
    with pytest.raises(ValueError, match="Word"):
        validate_attachment_file(filename="doc.docx", mime_type="", size_bytes=100)


def test_validate_rejects_pdf_over_50_pages():
    with pytest.raises(ValueError, match="50 页"):
        validate_attachment_file(
            filename="long.pdf",
            mime_type="application/pdf",
            size_bytes=1024,
            page_count=51,
        )


def test_validate_message_rejects_over_60_pages():
    with pytest.raises(ValueError, match="60 页"):
        validate_message_attachments(
            size_bytes_list=[100, 100],
            page_counts=[50, 11],
        )


def test_page_cost_rules():
    assert page_cost_for_kind(AttachmentKind.IMAGE) == 1
    assert page_cost_for_kind(AttachmentKind.SHEET) == 1
    assert page_cost_for_kind(AttachmentKind.TEXT) == 1
    assert page_cost_for_kind(AttachmentKind.PDF, pdf_pages=12) == 12
