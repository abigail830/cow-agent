"""Token/char budget preflight for attachment inline vs THIN send."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.platform.attachments.unify_lite.validation import is_unify_lite_image
from app.platform.memory.memory_config import AttachmentBudgetConfig

_IMAGE_CHAR_ESTIMATE = 8000


def count_unique_attachment_ids(items: list[dict[str, Any]]) -> int:
    return len(_unique_attachment_items(items))


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


def estimate_item_inline_chars(item: dict[str, Any], settings: Settings | None = None) -> int:
    """Rough char estimate if this attachment were FULL-inlined once."""
    s = settings or get_settings()
    snapshot = item.get("extracted_snapshot")
    if isinstance(snapshot, dict):
        char_count = snapshot.get("char_count")
        if isinstance(char_count, int) and char_count > 0:
            return char_count
        text = snapshot.get("text")
        if isinstance(text, str) and text:
            return len(text)
    size_bytes = item.get("size_bytes")
    if isinstance(size_bytes, int) and size_bytes > 0:
        if is_unify_lite_image(
            filename=str(item.get("filename") or ""),
            mime_type=str(item.get("mime_type") or ""),
        ):
            return max(_IMAGE_CHAR_ESTIMATE, size_bytes // 4)
        return min(size_bytes // 2, s.unify_lite_max_chars_per_file)
    return 2000


def estimate_inline_payload_chars(items: list[dict[str, Any]], settings: Settings | None = None) -> int:
    """Rough char estimate if all attachments were FULL-inlined on send."""
    total = 0
    for item in _unique_attachment_items(items):
        total += estimate_item_inline_chars(item, settings)
    return total


def inline_budget_limit(budget: AttachmentBudgetConfig, settings: Settings | None = None) -> int:
    s = settings or get_settings()
    if not budget.enabled:
        return int(s.unify_lite_max_chars_per_message)
    return int(s.unify_lite_max_chars_per_message * budget.safety_ratio)


def preflight_allows_full_inline(
    items: list[dict[str, Any]],
    budget: AttachmentBudgetConfig,
    settings: Settings | None = None,
) -> bool:
    """Return True when @mentioned attachments may be auto FULL-inlined on send."""
    if not budget.enabled:
        return True
    unique = _unique_attachment_items(items)
    if not unique:
        return True
    estimated = estimate_inline_payload_chars(unique, settings)
    return estimated <= inline_budget_limit(budget, settings)


def preflight_should_force_thin(
    items: list[dict[str, Any]],
    budget: AttachmentBudgetConfig,
    settings: Settings | None = None,
) -> bool:
    """Return True when send should use THIN instead of auto FULL inline."""
    return not preflight_allows_full_inline(items, budget, settings)


def check_inline_attachment_allowed(
    *,
    attachment_id: str,
    items: list[dict[str, Any]],
    budget: AttachmentBudgetConfig,
    already_inlined_ids: set[str] | None = None,
    settings: Settings | None = None,
) -> tuple[bool, str | None]:
    """Budget gate for inline_attachment tool (per-id, cumulative)."""
    if not budget.enabled:
        return True, None
    item_by_id = {str(item.get("id") or ""): item for item in _unique_attachment_items(items)}
    item = item_by_id.get(attachment_id)
    if item is None:
        return False, "Attachment is not part of the current turn context."
    inlined = set(already_inlined_ids or ())
    cumulative = estimate_inline_payload_chars(
        [item for att_id, item in item_by_id.items() if att_id in inlined or att_id == attachment_id],
        settings,
    )
    limit = inline_budget_limit(budget, settings)
    if cumulative > limit:
        return False, (
            f"Inline budget exceeded (estimated {cumulative} > {limit} chars). "
            "Use analyze_image or map_attachment for a cheaper summary, or reduce attachments."
        )
    return True, None
