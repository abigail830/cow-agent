from app.platform.attachments.materialization.plan import MaterializationAction, compute_attachment_plan
from app.platform.attachments.materialization.registry import AttachmentMaterializationRegistry
from app.platform.attachments.materialization.visibility import VisibilityIndex
from app.platform.attachments.services.preflight import (
    estimate_inline_payload_chars,
    preflight_allows_full_inline,
    preflight_should_force_thin,
)
from app.platform.memory.memory_config import AttachmentBudgetConfig, AttachmentPullConfig, MemoryConfig


def _doc_item(att_id: str, chars: int) -> dict:
    return {
        "id": att_id,
        "filename": f"{att_id}.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "extracted_snapshot": {"char_count": chars, "text": "x" * chars},
    }


def _image_item(att_id: str, size_bytes: int = 50_000) -> dict:
    return {
        "id": att_id,
        "filename": f"{att_id}.png",
        "mime_type": "image/png",
        "size_bytes": size_bytes,
    }


def test_preflight_three_small_attachments_allows_inline() -> None:
    items = [_doc_item("a1", 1000), _doc_item("a2", 1000), _doc_item("a3", 1000)]
    budget = AttachmentBudgetConfig(enabled=True)
    assert preflight_allows_full_inline(items, budget) is True
    assert preflight_should_force_thin(items, budget) is False


def test_preflight_over_budget_blocks_inline() -> None:
    items = [_doc_item("a1", 500_000), _doc_item("a2", 500_000)]
    budget = AttachmentBudgetConfig(enabled=True)
    assert preflight_allows_full_inline(items, budget) is False
    assert preflight_should_force_thin(items, budget) is True


def test_preflight_two_small_images_allows_inline() -> None:
    items = [_image_item("i1", 10_000), _image_item("i2", 10_000)]
    budget = AttachmentBudgetConfig(enabled=True)
    assert preflight_allows_full_inline(items, budget) is True


def test_preflight_disabled_always_allows_inline() -> None:
    items = [_doc_item("a1", 100_000), _doc_item("a2", 100_000), _doc_item("a3", 100_000)]
    budget = AttachmentBudgetConfig(enabled=False)
    assert preflight_allows_full_inline(items, budget) is True


def test_compute_plan_thin_for_three_even_when_budget_allows() -> None:
    """Multi-attachment never uses auto FULL on send — model chooses strategy."""
    items = [_doc_item("a1", 500), _doc_item("a2", 500), _doc_item("a3", 500)]
    plan = compute_attachment_plan(
        items=items,
        registry=AttachmentMaterializationRegistry(),
        visibility=VisibilityIndex(),
        user_text="我传了三个文件",
        turn_sequence=1,
        pull_config=AttachmentPullConfig(enabled=True, first_turn_inline=True),
        attachment_budget=AttachmentBudgetConfig(enabled=True),
    )
    assert all(item.action == MaterializationAction.THIN for item in plan)


def test_auto_full_only_single_attachment_no_entry_within_budget() -> None:
    items = [_image_item("i1", 10_000)]
    plan = compute_attachment_plan(
        items=items,
        registry=AttachmentMaterializationRegistry(),
        visibility=VisibilityIndex(),
        user_text="@i1.png",
        turn_sequence=1,
        pull_config=AttachmentPullConfig(enabled=True, first_turn_inline=True),
        attachment_budget=AttachmentBudgetConfig(enabled=True),
    )
    assert len(plan) == 1
    assert plan[0].action == MaterializationAction.FULL


def test_auto_full_not_when_registry_has_entry() -> None:
    registry = AttachmentMaterializationRegistry()
    registry.record_full_materialize(
        attachment_id="i1",
        content_hash="sha256:abc",
        materialized_kind="vision",
        filename="i1.png",
        turn_sequence=1,
    )
    items = [_image_item("i1", 10_000)]
    plan = compute_attachment_plan(
        items=items,
        registry=registry,
        visibility=VisibilityIndex(),
        user_text="@i1.png again",
        turn_sequence=3,
        pull_config=AttachmentPullConfig(enabled=True, first_turn_inline=True),
        attachment_budget=AttachmentBudgetConfig(enabled=True),
    )
    assert plan[0].action != MaterializationAction.FULL


def test_auto_full_not_when_over_budget() -> None:
    items = [_doc_item("a1", 500_000)]
    plan = compute_attachment_plan(
        items=items,
        registry=AttachmentMaterializationRegistry(),
        visibility=VisibilityIndex(),
        user_text="@big.docx",
        turn_sequence=1,
        pull_config=AttachmentPullConfig(enabled=True, first_turn_inline=True),
        attachment_budget=AttachmentBudgetConfig(enabled=True),
    )
    assert plan[0].action == MaterializationAction.THIN


def test_estimate_inline_payload_sums_snapshots() -> None:
    items = [_doc_item("a1", 3000), _doc_item("a2", 4000)]
    assert estimate_inline_payload_chars(items) == 7000
