"""Attachment facts + budget block for model-driven materialization strategy."""

from __future__ import annotations

from typing import Any

from app.config import Settings, get_settings
from app.platform.attachments.materialization.plan import AttachmentPlanItem, MaterializationAction
from app.platform.attachments.run_state import AttachmentRecord
from app.platform.attachments.services.preflight import (
    estimate_item_inline_chars,
    inline_budget_limit,
    preflight_allows_full_inline,
)
from app.platform.attachments.visibility_constants import (
    VISIBILITY_INLINED,
    VISIBILITY_NOT_INLINED,
    VISIBILITY_SUMMARY_ONLY,
)
from app.platform.memory.memory_config import AttachmentBudgetConfig


def visibility_for_action(action: MaterializationAction) -> str:
    if action == MaterializationAction.FULL:
        return VISIBILITY_INLINED
    if action == MaterializationAction.STUB:
        return VISIBILITY_SUMMARY_ONLY
    return VISIBILITY_NOT_INLINED


def record_turn_materialization_facts(
    *,
    mentioned_items: list[dict[str, Any]],
    plan: list[AttachmentPlanItem],
    budget: AttachmentBudgetConfig | None = None,
) -> None:
    """Store per-id visibility for the current turn on AttachmentRunState."""
    from app.platform.attachments.run_state import get_attachment_run_state

    state = get_attachment_run_state()
    if state is None:
        return

    budget_cfg = budget or AttachmentBudgetConfig()
    plan_by_id = {item.attachment_id: item for item in plan}
    mentioned_ids: list[str] = []
    visibility: dict[str, str] = {}
    inline_costs: dict[str, int] = {}

    for item in mentioned_items:
        if not isinstance(item, dict):
            continue
        att_id = str(item.get("id") or "")
        if not att_id:
            continue
        mentioned_ids.append(att_id)
        plan_item = plan_by_id.get(att_id)
        action = plan_item.action if plan_item else MaterializationAction.THIN
        visibility[att_id] = visibility_for_action(action)
        inline_costs[att_id] = estimate_item_inline_chars(item)

    allows = preflight_allows_full_inline(mentioned_items, budget_cfg)
    limit = inline_budget_limit(budget_cfg)
    total_est = sum(inline_costs.values())

    state.turn_mentioned_ids = mentioned_ids
    state.turn_visibility = visibility
    state.turn_inline_costs = inline_costs
    state.turn_inline_budget_limit = limit
    state.turn_inline_budget_allows_full = allows
    state.turn_inline_budget_total_est = total_est


def format_facts_and_budget_block(
    records: list[AttachmentRecord],
    *,
    budget: AttachmentBudgetConfig | None = None,
) -> str:
    """Format attachment availability facts + inline budget for the orchestrator."""
    from app.platform.attachments.catalog.formatter import attachment_kind
    from app.platform.attachments.run_state import get_attachment_run_state

    state = get_attachment_run_state()
    budget_cfg = budget or AttachmentBudgetConfig()
    settings = get_settings()
    limit = inline_budget_limit(budget_cfg, settings)

    lines = ["[Attachment facts + budget]"]
    if state is not None:
        remaining = max(0, limit - state.turn_inline_budget_total_est)
        if state.turn_visibility:
            lines.append(f"inline_budget_limit_est: {limit}")
            lines.append(f"inline_budget_remaining_est: {remaining}")
            lines.append(f"auto_inline_allowed: {state.turn_inline_budget_allows_full}")
            lines.append("@mentioned_this_turn:")
            for att_id in state.turn_mentioned_ids:
                record = next((r for r in records if str(r.attachment_id) == att_id), None)
                filename = record.filename if record else att_id
                kind = attachment_kind(record) if record else "unknown"
                vis = state.turn_visibility.get(att_id, VISIBILITY_NOT_INLINED)
                cost = state.turn_inline_costs.get(att_id, 0)
                lines.append(
                    f"  - id={att_id} filename={filename} kind={kind} "
                    f"visibility={vis} inline_cost_est={cost}"
                )
        if state.map_cache:
            lines.append(f"cached_summaries: {len(state.map_cache)} available")
        lines.append(
            "Tools (choose by task + budget; do NOT call analyze_image when visibility=inlined_this_turn):"
        )
        lines.append("  inline_attachment — request direct pixels in your context (costs inline budget)")
        lines.append("  analyze_image — worker text summary (cheaper when pixels not needed)")
        lines.append("  map_attachment — batch summarize per id")
        lines.append("  read_attachment — verbatim document text")
    else:
        lines.append("inline_budget_limit_est: " + str(limit))

    if records:
        lines.append("catalog:")
        for record in sorted(records, key=lambda item: str(item.attachment_id)):
            gist = (record.gist or record.filename).replace("\n", " ").strip()
            kind = attachment_kind(record)
            vis = (
                state.turn_visibility.get(str(record.attachment_id), VISIBILITY_NOT_INLINED)
                if state is not None
                else VISIBILITY_NOT_INLINED
            )
            lines.append(
                f"  - id={record.attachment_id} filename={record.filename} "
                f'gist="{gist}" kind={kind} visibility={vis}'
            )

    return "\n".join(lines)
