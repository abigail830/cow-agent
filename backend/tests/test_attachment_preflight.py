from app.platform.attachments.materialization.plan import MaterializationAction, compute_attachment_plan
from app.platform.attachments.materialization.registry import AttachmentMaterializationRegistry
from app.platform.attachments.materialization.visibility import VisibilityIndex
from app.platform.attachments.services.preflight import (
    estimate_inline_payload_chars,
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


def test_preflight_three_attachments_forces_thin() -> None:
    items = [_doc_item("a1", 1000), _doc_item("a2", 1000), _doc_item("a3", 1000)]
    budget = AttachmentBudgetConfig(enabled=True)
    assert preflight_should_force_thin(items, budget) is True


def test_preflight_two_small_images_allows_inline() -> None:
    items = [_image_item("i1", 10_000), _image_item("i2", 10_000)]
    budget = AttachmentBudgetConfig(enabled=True)
    assert preflight_should_force_thin(items, budget) is False


def test_preflight_disabled_never_forces_thin() -> None:
    items = [_doc_item("a1", 100_000), _doc_item("a2", 100_000), _doc_item("a3", 100_000)]
    budget = AttachmentBudgetConfig(enabled=False)
    assert preflight_should_force_thin(items, budget) is False


def test_compute_plan_thin_for_three_on_first_send() -> None:
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


def test_estimate_inline_payload_sums_snapshots() -> None:
    items = [_doc_item("a1", 3000), _doc_item("a2", 4000)]
    assert estimate_inline_payload_chars(items) == 7000
