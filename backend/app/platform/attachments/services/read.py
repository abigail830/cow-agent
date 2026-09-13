"""Read / extract text from chat attachments (map + read_attachment backing)."""

from __future__ import annotations

from app.config import Settings, get_settings
from app.platform.attachments.unify_lite.extractors.registry import extract_bytes
from app.platform.attachments.unify_lite.truncate import truncate_chars


class AttachmentReadService:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def extract_text(
        self,
        *,
        filename: str,
        mime_type: str,
        data: bytes,
        query: str | None = None,
        max_chars: int | None = None,
    ) -> tuple[str, list[str], bool]:
        """Return (text, warnings, truncated)."""
        limit = max_chars if max_chars is not None else self._settings.unify_lite_max_chars_per_file
        content, warnings, _ = extract_bytes(
            filename=filename,
            mime_type=mime_type,
            data=data,
        )
        if query:
            needle = query.strip().lower()
            if needle:
                lines = [line for line in content.splitlines() if needle in line.lower()]
                content = "\n".join(lines) if lines else f"(No lines matched query: {query})"

        truncated = False
        if len(content) > limit:
            content, truncated = truncate_chars(content, limit)
        return content, list(warnings), truncated
