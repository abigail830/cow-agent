"""Image sniffing, validation, and LLM-safe normalization (PyMuPDF)."""

from __future__ import annotations

import pymupdf as fitz

from app.platform.attachments.kinds import file_extension, normalize_mime

# DeepSeek / most OpenAI-compatible vision APIs reject images above 8192 px per side
# (they often return a misleading "unsupported image" error instead of "too large").
LLM_VISION_MAX_SIDE = 8192

_IMAGE_MIMES = frozenset({"image/png", "image/jpeg", "image/gif", "image/webp"})
_EXT_TO_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def sniff_image_mime(data: bytes) -> str | None:
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 3 and data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if len(data) >= 6 and data[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def resolve_image_mime(*, data: bytes, filename: str, mime_type: str | None) -> str:
    sniffed = sniff_image_mime(data)
    if sniffed:
        return sniffed
    declared = normalize_mime(mime_type)
    if declared in _IMAGE_MIMES:
        return declared
    ext = file_extension(filename)
    if ext in _EXT_TO_MIME:
        return _EXT_TO_MIME[ext]
    raise ValueError(f"Unsupported or unreadable image: {filename}")


def validate_image_bytes(data: bytes, *, filename: str) -> None:
    try:
        fitz.Pixmap(data)
    except Exception as exc:
        raise ValueError(
            f"附件 {filename} 不是有效的图片（PNG/JPEG/GIF/WebP），请重新上传。"
        ) from exc


def _cap_pixmap_side(pix: fitz.Pixmap, *, max_side: int = LLM_VISION_MAX_SIDE) -> fitz.Pixmap:
    """Downscale oversized exports (e.g. Figma @2x) to provider limits."""
    capped = pix
    while max(capped.width, capped.height) > max_side:
        capped.shrink(1)
    return capped


def normalize_image_for_llm(data: bytes) -> tuple[bytes, str]:
    """Re-encode to RGB JPEG/PNG so vision APIs accept the payload."""
    pix = _cap_pixmap_side(fitz.Pixmap(data))
    if pix.alpha or pix.n - pix.alpha >= 4:
        rgb = fitz.Pixmap(fitz.csRGB, pix)
        pix = rgb
    if pix.alpha:
        normalized = pix.tobytes(output="png")
    else:
        normalized = pix.tobytes(output="jpeg", jpg_quality=90)
    sniffed = sniff_image_mime(normalized)
    if not sniffed:
        raise ValueError("Failed to produce a valid image payload for the model")
    return normalized, sniffed


def prepare_image_for_storage(
    data: bytes,
    *,
    filename: str,
    mime_type: str | None,
) -> tuple[bytes, str]:
    """Validate, normalize bytes, and return canonical mime for persistence."""
    resolved = resolve_image_mime(data=data, filename=filename, mime_type=mime_type)
    validate_image_bytes(data, filename=filename)
    normalized, canonical = normalize_image_for_llm(data)
    if canonical != resolved:
        return normalized, canonical
    # Still normalize to strip exotic color spaces / bit depths even when mime matches.
    return normalized, canonical
