from app.platform.attachments.unify_lite.extractors.registry import extract_bytes
from app.platform.attachments.unify_lite.extractors.text import decode_text_bytes
from app.platform.attachments.unify_lite.validation import is_unify_lite_file


def test_is_unify_lite_file_by_extension() -> None:
    assert is_unify_lite_file(filename="notes.txt", mime_type="text/plain")
    assert is_unify_lite_file(filename="readme.md", mime_type="text/plain")
    assert is_unify_lite_file(
        filename="report.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert not is_unify_lite_file(filename="scan.pdf", mime_type="application/pdf")


def test_extract_plain_text() -> None:
    content, warnings, _elapsed = extract_bytes(
        filename="hello.txt",
        mime_type="text/plain",
        data="你好 unify-lite".encode(),
    )
    assert "你好 unify-lite" in content
    assert warnings == []


def test_decode_utf8_sig() -> None:
    assert decode_text_bytes("hi".encode("utf-8-sig")) == "hi"
