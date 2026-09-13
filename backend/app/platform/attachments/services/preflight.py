"""Token/char budget preflight for attachment inline vs THIN send."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.platform.attachments.unify_lite.validation import is_unify_lite_image
from app.platform.memory.memory_config import AttachmentBudgetConfig

_IMAGE_CHAR_ESTIMATE = 8000


def _unique_attachment_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        att_id = str(item.get("id") or "")
        if not att_id or att_id in seen:
            continue
        seen.add(att_id)
        unique.append(item)
    return unique


def estimate_inline_payload_chars(items: list[dict[str, Any]], settings: Settings | None = None) -> int:
    """Rough char estimate if all attachments were FULL-inlined on send."""
    s = settings or get_settings()
    total = 0
    for item in _unique_attachment_items(items):
        snapshot = item.get("extracted_snapshot")
        if isinstance(snapshot, dict):
            char_count = snapshot.get("char_count")
            if isinstance(char_count, int) and char_count > 0:
                total += char_count
                continue
            text = snapshot.get("text")
            if isinstance(text, str) and text:
                total += len(text)
                continue
        size_bytes = item.get("size_bytes")
        if isinstance(size_bytes, int) and size_bytes > 0:
            if is_unify_lite_image(
                filename=str(item.get("filename") or ""),
                mime_type=str(item.get("mime_type") or ""),
            ):
                total += max(_IMAGE_CHAR_ESTIMATE, size_bytes // 4)
            else:
                total += min(size_bytes // 2, s.unify_lite_max_chars_per_file)
            continue
        total += 2000
    return total


def preflight_should_force_thin(
    items: list[dict[str, Any]],
    budget: AttachmentBudgetConfig,
    settings: Settings | None = None,
) -> bool:
    """Return True when send should use THIN + catalog instead of FULL inline."""
    if not budget.enabled:
        return False
    unique = _unique_attachment_items(items)
    if not unique:
        return False
    s = settings or get_settings()
    estimated = estimate_inline_payload_chars(unique, s)
    limit = int(s.unify_lite_max_chars_per_message * budget.safety_ratio)
    if estimated > limit:
        return True
    if len(unique) >= 3:
        return True
    return False
