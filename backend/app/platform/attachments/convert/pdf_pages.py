"""PDF page count and JPEG rasterization via PyMuPDF (no poppler)."""

from __future__ import annotations

from dataclasses import dataclass

DEFAULT_PDF_ZOOM = 2.0  # ~144 dpi
DEFAULT_JPEG_QUALITY = 85


@dataclass(frozen=True)
class PdfPageImage:
    index: int
    data: bytes
    mime_type: str = "image/jpeg"
    filename: str = ""


def count_pdf_pages(data: bytes) -> int:
    import fitz

    document = fitz.open(stream=data, filetype="pdf")
    try:
        return int(document.page_count)
    finally:
        document.close()


def rasterize_pdf_pages(
    data: bytes,
    *,
    filename: str = "document.pdf",
    zoom: float = DEFAULT_PDF_ZOOM,
    jpeg_quality: int = DEFAULT_JPEG_QUALITY,
    max_pages: int | None = None,
) -> list[PdfPageImage]:
    import fitz

    document = fitz.open(stream=data, filetype="pdf")
    pages: list[PdfPageImage] = []
    stem = filename.rsplit(".", 1)[0] if filename else "document"
    try:
        limit = document.page_count if max_pages is None else min(document.page_count, max_pages)
        matrix = fitz.Matrix(zoom, zoom)
        for index in range(limit):
            page = document.load_page(index)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            jpeg = pixmap.tobytes(output="jpeg", jpg_quality=jpeg_quality)
            pages.append(
                PdfPageImage(
                    index=index + 1,
                    data=jpeg,
                    filename=f"{stem}-p{index + 1}.jpg",
                )
            )
    finally:
        document.close()
    return pages
