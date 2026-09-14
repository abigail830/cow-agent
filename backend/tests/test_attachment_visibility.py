import uuid

import pytest

from app.platform.attachments.materialization.plan import MaterializationAction, compute_attachment_plan
from app.platform.attachments.materialization.registry import AttachmentMaterializationRegistry
from app.platform.attachments.materialization.replay import build_materialized_user_message, count_image_data_blocks
from app.platform.attachments.materialization.visibility import (
    VisibilityIndex,
    build_visibility_index,
    project_rows_for_visibility,
)
from app.platform.attachments.materialization.compaction import strip_attachment_heavy_payload
from app.platform.memory.memory_config import AttachmentCompactionConfig, AttachmentPullConfig, MemoryConfig, parse_memory_config


CHAT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ATTACHMENT_ID = "22222222-2222-2222-2222-222222222222"


def _image_meta() -> dict:
    return {
        "id": ATTACHMENT_ID,
        "filename": "chart.png",
        "mime_type": "image/png",
        "size_bytes": 64,
        "provider": "unify_lite",
        "provider_file_id": f"inline:{ATTACHMENT_ID}",
        "content_hash": "sha256:img001",
    }


def _user_row(*, sequence: int, content: str = "@chart.png") -> dict:
    return {
        "id": str(uuid.uuid4()),
        "chat_id": str(CHAT_ID),
        "role": "user",
        "message_type": "text",
        "content": content,
        "sequence": sequence,
        "metadata": {"attachment_mode": "unify_lite", "attachments": [_image_meta()]},
    }


@pytest.fixture(autouse=True)
def _mock_image_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.platform.attachments.native.maf_content.load_inline_attachment",
        lambda _chat_id, _attachment_id: b"\x89PNG\r\n",
    )


def test_stub_forbidden_when_anchor_compacted() -> None:
    rows = [_user_row(sequence=1)]
    for seq in (3, 5):
        filler = _user_row(sequence=seq)
        filler["content"] = f"turn {seq}"
        filler["metadata"] = {"attachment_mode": "unify_lite", "attachments": []}
        rows.append(filler)
    compacted = strip_attachment_heavy_payload(
        rows[0],
        rows=rows,
        compaction=AttachmentCompactionConfig(enabled=True, keep_full_turns=1),
    )
    memory_config = parse_memory_config({"memory": {"attachment_pull": {"enabled": False}}})
    projected = [compacted, rows[1], rows[2]]
    visibility = build_visibility_index(projected)
    registry = AttachmentMaterializationRegistry()
    registry.seed_from_prior_rows(projected, memory_config=memory_config)

    plan = compute_attachment_plan(
        items=[_image_meta()],
        registry=registry,
        visibility=visibility,
        user_text="@chart.png again",
        turn_sequence=3,
        pull_config=memory_config.attachment_pull,
    )
    assert plan[0].action == MaterializationAction.FULL


def test_same_turn_duplicate_attachment_id_plans_once() -> None:
    registry = AttachmentMaterializationRegistry()
    visibility = VisibilityIndex()
    items = [_image_meta(), dict(_image_meta())]
    plan = compute_attachment_plan(
        items=items,
        registry=registry,
        visibility=visibility,
        user_text="@chart.png",
        turn_sequence=1,
        pull_config=AttachmentPullConfig(enabled=False),
    )
    assert plan[0].action == MaterializationAction.FULL
    assert plan[1].action == MaterializationAction.SKIP


def _native_image_meta(att_id: str, filename: str) -> dict:
    return {
        "id": att_id,
        "filename": filename,
        "mime_type": "image/jpeg",
        "size_bytes": 64,
        "provider": "deepseek",
        "processing_mode": "native",
        "provider_file_id": f"inline:{att_id}",
        "content_hash": f"sha256:{att_id}",
    }


def test_native_three_images_full_inline_even_when_pull_enabled() -> None:
    ids = [
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1",
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2",
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa3",
    ]
    items = [_native_image_meta(att_id, f"{idx + 1}.jpeg") for idx, att_id in enumerate(ids)]
    run_input = build_materialized_user_message(
        "看这三张图",
        {"attachment_mode": "native", "attachments": items},
        chat_id=CHAT_ID,
        turn_sequence=1,
        registry=AttachmentMaterializationRegistry(),
        visibility=VisibilityIndex(),
        pull_config=AttachmentPullConfig(enabled=True, first_turn_inline=True),
    )
    assert count_image_data_blocks(run_input.contents) == 3


def test_pull_mode_second_at_is_stub_not_full() -> None:
    memory_config = MemoryConfig()
    projected = project_rows_for_visibility([_user_row(sequence=1)], memory_config)
    visibility = build_visibility_index(projected)
    registry = AttachmentMaterializationRegistry()
    registry.seed_from_prior_rows([_user_row(sequence=1)], memory_config=memory_config)
    run_input = build_materialized_user_message(
        "@chart.png again",
        {"attachment_mode": "unify_lite", "attachments": [_image_meta()]},
        chat_id=CHAT_ID,
        turn_sequence=3,
        registry=registry,
        visibility=visibility,
        pull_config=AttachmentPullConfig(enabled=True, first_turn_inline=True),
    )
    assert count_image_data_blocks(run_input.contents) == 0
    text = " ".join(getattr(c, "text", "") or "" for c in run_input.contents)
    assert "Attachment reference" in text
