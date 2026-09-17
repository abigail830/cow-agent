"""Content-Disposition must stay latin-1-safe for Starlette Response headers."""

from starlette.responses import Response

from app.shared.artifacts.urls import content_disposition_attachment


def test_ascii_filename_disposition() -> None:
    value = content_disposition_attachment("deck.pptx")
    assert 'filename="deck.pptx"' in value
    assert "filename*=UTF-8''deck.pptx" in value
    Response(content=b"x", headers={"Content-Disposition": value})


def test_cjk_filename_disposition_is_latin1_safe() -> None:
    value = content_disposition_attachment("COSMOS Outcome 5 功能蓝图.pptx")
    assert "功能" not in value.split("filename*=")[0]
    assert "UTF-8''" in value
    assert "%E5%8A%9F%E8%83%BD" in value
    # Starlette encodes header values as latin-1; this must not raise.
    Response(content=b"x", headers={"Content-Disposition": value})
