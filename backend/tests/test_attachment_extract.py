from app.platform.attachments.convert.pdf_pages import count_pdf_pages, rasterize_pdf_pages
from app.platform.attachments.extract.tables import extract_sheet_bytes
from app.platform.attachments.extract.text import decode_text_bytes


def _minimal_pdf(pages: int = 1) -> bytes:
    import fitz

    document = fitz.open()
    try:
        for index in range(pages):
            page = document.new_page()
            page.insert_text((72, 72), f"page {index + 1}")
        return document.tobytes()
    finally:
        document.close()


def test_decode_text_prefers_utf8_and_gb18030():
    assert decode_text_bytes("你好".encode("utf-8")) == "你好"
    assert decode_text_bytes("你好".encode("gb18030")) == "你好"


def test_extract_csv_as_markdown():
    data = b"name,qty\nA,1\nB,2\n"
    text, warnings = extract_sheet_bytes(data, filename="grid.csv")
    assert "name" in text and "qty" in text
    assert "A" in text
    assert warnings == []


def test_count_and_rasterize_pdf_pages():
    data = _minimal_pdf(2)
    assert count_pdf_pages(data) == 2
    pages = rasterize_pdf_pages(data, filename="deck.pdf")
    assert len(pages) == 2
    assert pages[0].mime_type == "image/jpeg"
    assert pages[0].data[:2] == b"\xff\xd8"
    assert pages[0].filename == "deck-p1.jpg"
