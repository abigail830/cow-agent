"""Unified materialization plan — send and replay share visibility-aware decisions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from app.platform.attachments.materialization.registry import AttachmentMaterializationRegistry
from app.platform.attachments.materialization.stub import user_requests_force_reread
from app.platform.attachments.materialization.visibility import VisibilityIndex
from app.platform.attachments.services.preflight import preflight_should_force_thin
from app.platform.memory.memory_config import AttachmentBudgetConfig, AttachmentPullConfig


class MaterializationAction(str, Enum):
    FULL = "full"
    STUB = "stub"
    THIN = "thin"
    SKIP = "skip"


@dataclass(frozen=True)
class AttachmentPlanItem:
    attachment_id: str
    action: MaterializationAction
    hash_changed: bool = False


def compute_attachment_plan(
    *,
    items: list[dict[str, Any]],
    registry: AttachmentMaterializationRegistry,
    visibility: VisibilityIndex,
    user_text: str,
    turn_sequence: int,
    pull_config: AttachmentPullConfig | None = None,
    attachment_budget: AttachmentBudgetConfig | None = None,
) -> list[AttachmentPlanItem]:
    """Decide FULL / STUB / THIN for each attachment in one user turn."""
    pull = pull_config or AttachmentPullConfig()
    budget = attachment_budget or AttachmentBudgetConfig()
    force_reread = user_requests_force_reread(user_text) if not pull.enabled else False
    item_dicts = [item for item in items if isinstance(item, dict)]
    force_thin = preflight_should_force_thin(item_dicts, budget) if pull.enabled else False
    seen_ids: set[str] = set()
    plans: list[AttachmentPlanItem] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        att_id = str(item.get("id") or "")
        if not att_id:
            continue
        if att_id in seen_ids:
            plans.append(AttachmentPlanItem(att_id, MaterializationAction.SKIP))
            continue
        seen_ids.add(att_id)

        if item.get("compaction_placeholder"):
            plans.append(AttachmentPlanItem(att_id, MaterializationAction.FULL))
            continue

        content_hash = _attachment_content_hash(item)
        entry = registry.get_entry(att_id)

        if pull.enabled:
            if entry is None:
                if force_thin:
                    action = MaterializationAction.THIN
                else:
                    action = (
                        MaterializationAction.FULL
                        if pull.first_turn_inline
                        else MaterializationAction.THIN
                    )
                plans.append(AttachmentPlanItem(att_id, action))
                continue
            if content_hash and entry.content_hash and entry.content_hash != content_hash:
                plans.append(AttachmentPlanItem(att_id, MaterializationAction.FULL, hash_changed=True))
                continue
            plans.append(AttachmentPlanItem(att_id, MaterializationAction.THIN))
            continue

        full, hash_changed = registry.should_full_materialize(
            att_id,
            content_hash,
            force_reread=force_reread,
            visibility=visibility,
        )
        if full:
            plans.append(AttachmentPlanItem(att_id, MaterializationAction.FULL, hash_changed=hash_changed))
            continue

        anchor = registry.last_full_inject_turn(att_id)
        if visibility.anchor_still_visible(att_id, anchor):
            plans.append(AttachmentPlanItem(att_id, MaterializationAction.STUB))
        else:
            plans.append(AttachmentPlanItem(att_id, MaterializationAction.FULL))

    return plans


def _attachment_content_hash(item: dict[str, Any]) -> str:
    snapshot = item.get("extracted_snapshot")
    if isinstance(snapshot, dict):
        value = str(snapshot.get("content_hash") or "")
        if value:
            return value
    return str(item.get("content_hash") or "")
