from __future__ import annotations

import base64
import binascii
import hashlib
import logging
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_DATA_IMAGE_URI_RE = re.compile(
    r"^data:image/(png|jpe?g|gif|webp);base64,([A-Za-z0-9+/=\s]+)$",
    re.IGNORECASE,
)
_FIGURE_REF_SCHEME = "figure:"
_FIGURE_MAX_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class MirroredFigure:
    figure_id: str
    alt: str
    line: int
    data: bytes
    mime_type: str
    extension: str
    source_url: str
    sha256: str


@dataclass(frozen=True)
class FigureMirrorResult:
    content_md: str
    figures: tuple[MirroredFigure, ...]
    warnings: tuple[str, ...]


def _guess_extension(mime_type: str, url: str) -> str:
    normalized = (mime_type or "").split(";", 1)[0].strip().lower()
    if normalized == "image/jpeg":
        return "jpeg"
    if normalized == "image/png":
        return "png"
    if normalized == "image/gif":
        return "gif"
    if normalized == "image/webp":
        return "webp"
    path = urlparse(url).path.lower()
    for ext in ("jpeg", "jpg", "png", "gif", "webp"):
        if path.endswith(f".{ext}"):
            return "jpeg" if ext == "jpg" else ext
    return "jpeg"


def _mime_from_data_uri_format(fmt: str) -> str:
    normalized = fmt.strip().lower()
    if normalized in {"jpg", "jpeg"}:
        return "image/jpeg"
    return f"image/{normalized}"


def _validate_image_magic(data: bytes, mime_type: str) -> bool:
    if mime_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime_type == "image/gif":
        return data.startswith(b"GIF87a") or data.startswith(b"GIF89a")
    if mime_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def _is_remote_image_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"}


def _is_data_image_uri(url: str) -> bool:
    return _DATA_IMAGE_URI_RE.match(url.strip()) is not None


def _decode_data_uri_image(url: str) -> tuple[bytes, str]:
    match = _DATA_IMAGE_URI_RE.match(url.strip())
    if match is None:
        raise ValueError("unsupported data URI")
    fmt = match.group(1)
    payload = re.sub(r"\s+", "", match.group(2))
    try:
        data = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("invalid base64 payload") from exc
    if len(data) > _FIGURE_MAX_BYTES:
        raise ValueError(f"decoded image exceeds {_FIGURE_MAX_BYTES} bytes")
    mime_type = _mime_from_data_uri_format(fmt)
    if not _validate_image_magic(data, mime_type):
        raise ValueError("image bytes do not match declared mime type")
    return data, mime_type


def _download_image(url: str, *, timeout_sec: float = 120.0, retries: int = 3) -> tuple[bytes, str]:
    last_exc: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
                response = client.get(url)
                response.raise_for_status()
                content_type = (response.headers.get("content-type") or "application/octet-stream").split(";", 1)[0]
                return response.content, content_type.strip().lower()
        except Exception as exc:
            last_exc = exc
            if attempt + 1 < retries:
                time.sleep(float(attempt + 1))
                continue
            raise
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("figure download failed")


def _materialize_figure(
    *,
    alt: str,
    line_no: int,
    figure_id: str,
    url: str,
    data: bytes,
    mime_type: str,
) -> MirroredFigure:
    ext = _guess_extension(mime_type, url)
    digest = hashlib.sha256(data).hexdigest()
    return MirroredFigure(
        figure_id=figure_id,
        alt=alt,
        line=line_no,
        data=data,
        mime_type=mime_type,
        extension=ext,
        source_url=url,
        sha256=digest,
    )


def mirror_markdown_figures(content_md: str) -> FigureMirrorResult:
    """Materialize remote and data-URI markdown images as figure:fN refs."""

    warnings: list[str] = []
    figures: list[MirroredFigure] = []
    figure_index = 0
    lines = content_md.splitlines(keepends=True)
    output_lines: list[str] = []
    line_no = 0

    for line in lines:
        line_no += 1
        cursor = 0
        pieces: list[str] = []
        for match in _MARKDOWN_IMAGE_RE.finditer(line):
            start, end = match.span()
            pieces.append(line[cursor:start])
            alt = match.group(1)
            url = match.group(2).strip()
            if url.startswith(_FIGURE_REF_SCHEME):
                pieces.append(match.group(0))
            elif _is_data_image_uri(url):
                figure_index += 1
                figure_id = f"f{figure_index}"
                try:
                    data, mime_type = _decode_data_uri_image(url)
                    figures.append(
                        _materialize_figure(
                            alt=alt,
                            line_no=line_no,
                            figure_id=figure_id,
                            url=url,
                            data=data,
                            mime_type=mime_type,
                        )
                    )
                    pieces.append(f"![{alt}]({_FIGURE_REF_SCHEME}{figure_id})")
                except Exception as exc:
                    logger.warning("figure data-uri decode failed id=%s error=%s", figure_id, exc)
                    warnings.append(f"figure_data_uri_failed:{figure_id}:{exc}")
                    pieces.append(match.group(0))
            elif _is_remote_image_url(url):
                figure_index += 1
                figure_id = f"f{figure_index}"
                try:
                    data, mime_type = _download_image(url)
                    if len(data) > _FIGURE_MAX_BYTES:
                        raise ValueError(f"downloaded image exceeds {_FIGURE_MAX_BYTES} bytes")
                    figures.append(
                        _materialize_figure(
                            alt=alt,
                            line_no=line_no,
                            figure_id=figure_id,
                            url=url,
                            data=data,
                            mime_type=mime_type,
                        )
                    )
                    pieces.append(f"![{alt}]({_FIGURE_REF_SCHEME}{figure_id})")
                except Exception as exc:
                    logger.warning("figure mirror failed url=%s error=%s", url[:120], exc)
                    warnings.append(f"figure_mirror_failed:{figure_id}:{exc}")
                    pieces.append(match.group(0))
            else:
                pieces.append(match.group(0))
            cursor = end
        pieces.append(line[cursor:])
        output_lines.append("".join(pieces))

    return FigureMirrorResult(
        content_md="".join(output_lines),
        figures=tuple(figures),
        warnings=tuple(warnings),
    )


def figures_to_meta(figures: tuple[MirroredFigure, ...]) -> list[dict[str, Any]]:
    return [
        {
            "id": fig.figure_id,
            "line": fig.line,
            "alt": fig.alt,
            "mime": fig.mime_type,
            "size_bytes": len(fig.data),
            "sha256": fig.sha256,
            "filename": f"{fig.figure_id}.{fig.extension}",
        }
        for fig in figures
    ]
