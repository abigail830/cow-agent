"""Resize chat images before vision mini-requests."""

from __future__ import annotations

import io
from dataclasses import dataclass


@dataclass(frozen=True)
class ResizedImage:
    data: bytes
    media_type: str
    width: int
    height: int
    resized: bool


def resize_image_for_vision(
    data: bytes,
    *,
    mime_type: str,
    max_edge: int,
    jpeg_quality: int = 85,
) -> ResizedImage:
    """Downscale large images; PNG/GIF/WebP convert to JPEG when resized."""
    try:
        from PIL import Image
    except ImportError:
        return ResizedImage(data=data, media_type=mime_type, width=0, height=0, resized=False)

    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            width, height = image.size
            longest = max(width, height)
            if longest <= max_edge:
                return ResizedImage(
                    data=data,
                    media_type=mime_type,
                    width=width,
                    height=height,
                    resized=False,
                )

            scale = max_edge / float(longest)
            new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            converted = image.convert("RGB")
            resized = converted.resize(new_size, Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            resized.save(buffer, format="JPEG", quality=jpeg_quality, optimize=True)
            return ResizedImage(
                data=buffer.getvalue(),
                media_type="image/jpeg",
                width=new_size[0],
                height=new_size[1],
                resized=True,
            )
    except OSError:
        return ResizedImage(data=data, media_type=mime_type, width=0, height=0, resized=False)
