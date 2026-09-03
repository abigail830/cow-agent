"""Platform attachment limits — read from Settings (.env), shared by all agents."""

from __future__ import annotations

from functools import lru_cache

from app.config import Settings, get_settings


@lru_cache
def _limits_from_settings() -> tuple[int, int, int]:
    settings = get_settings()
    return (
        settings.attachment_max_files_per_message,
        settings.attachment_max_bytes_per_file,
        settings.attachment_max_total_bytes_per_message,
    )


def attachment_limits(settings: Settings | None = None) -> tuple[int, int, int]:
    if settings is None:
        return _limits_from_settings()
    return (
        settings.attachment_max_files_per_message,
        settings.attachment_max_bytes_per_file,
        settings.attachment_max_total_bytes_per_message,
    )


def attachment_limits_dict(settings: Settings | None = None) -> dict[str, int]:
    max_files, max_file_bytes, max_total_bytes = attachment_limits(settings)
    return {
        "max_files_per_message": max_files,
        "max_bytes_per_file": max_file_bytes,
        "max_total_bytes_per_message": max_total_bytes,
    }
