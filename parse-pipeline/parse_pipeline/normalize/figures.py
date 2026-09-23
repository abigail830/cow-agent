from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_FIGURE_REF_SCHEME = "figure:"


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


def _should_mirror_url(url: str) -> bool:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    if parsed.scheme == "figure":
        return False
    return True


def _download_image(url: str, *, timeout_sec: float = 60.0) -> tuple[bytes, str]:
    with httpx.Client(timeout=timeout_sec, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        content_type = (response.headers.get("content-type") or "application/octet-stream").split(";", 1)[0]
        return response.content, content_type.strip().lower()


def mirror_markdown_figures(content_md: str) -> FigureMirrorResult:
    """Download remote markdown images and rewrite refs to figure:fN."""

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
            if not _should_mirror_url(url):
                pieces.append(match.group(0))
            else:
                figure_index += 1
                figure_id = f"f{figure_index}"
                try:
                    data, mime_type = _download_image(url)
                    ext = _guess_extension(mime_type, url)
                    digest = hashlib.sha256(data).hexdigest()
                    figures.append(
                        MirroredFigure(
                            figure_id=figure_id,
                            alt=alt,
                            line=line_no,
                            data=data,
                            mime_type=mime_type,
                            extension=ext,
                            source_url=url,
                            sha256=digest,
                        )
                    )
                    pieces.append(f"![{alt}]({_FIGURE_REF_SCHEME}{figure_id})")
                except Exception as exc:
                    logger.warning("figure mirror failed url=%s error=%s", url[:120], exc)
                    warnings.append(f"figure_mirror_failed:{figure_id}:{exc}")
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
