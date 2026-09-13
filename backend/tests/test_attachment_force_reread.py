import uuid

import pytest

from app.platform.attachments.materialization.replay import build_materialized_user_message
from app.platform.attachments.materialization.registry import AttachmentMaterializationRegistry
from app.platform.attachments.materialization.replay import count_image_data_blocks
from app.platform.memory.memory_config import AttachmentPullConfig, parse_memory_config
from app.platform.attachments.materialization.visibility import build_visibility_index, project_rows_for_visibility

PUSH_PULL = AttachmentPullConfig(enabled=False)


CHAT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ATTACHMENT_ID = "22222222-2222-2222-2222-222222222222"


def _prior_row(sequence: int) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "chat_id": str(CHAT_ID),
        "role": "user",
        "message_type": "text",
        "content": "Analyze @chart.png",
        "sequence": sequence,
        "metadata": {
            "attachment_mode": "unify_lite",
            "attachments": [
                {
                    "id": ATTACHMENT_ID,
                    "filename": "chart.png",
                    "mime_type": "image/png",
                    "size_bytes": 64,
                    "provider": "unify_lite",
                    "provider_file_id": f"inline:{ATTACHMENT_ID}",
                    "content_hash": "sha256:img001",
                }
            ],
        },
    }


@pytest.fixture(autouse=True)
def _mock_image_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.platform.attachments.native.maf_content.load_inline_attachment",
        lambda _chat_id, _attachment_id: b"\x89PNG\r\n",
    )


def test_force_reread_phrase_triggers_full_image() -> None:
    memory_config = parse_memory_config({"memory": {"attachment_pull": {"enabled": False}}})
    projected = project_rows_for_visibility([_prior_row(1), _prior_row(3)], memory_config)
    visibility = build_visibility_index(projected)
    registry = AttachmentMaterializationRegistry()
    registry.seed_from_prior_rows([_prior_row(1), _prior_row(3)], memory_config=memory_config)

    metadata = {
        "attachment_mode": "unify_lite",
        "attachments": [_prior_row(1)["metadata"]["attachments"][0]],
    }
    run_input = build_materialized_user_message(
        "请再看一遍 @chart.png 确认颜色",
        metadata,
        chat_id=CHAT_ID,
        turn_sequence=5,
        registry=registry,
        visibility=visibility,
        pull_config=PUSH_PULL,
    )
    assert count_image_data_blocks(run_input.contents) == 1


def test_stub_contains_attachment_id() -> None:
    memory_config = parse_memory_config({"memory": {"attachment_pull": {"enabled": False}}})
    projected = project_rows_for_visibility([_prior_row(1)], memory_config)
    visibility = build_visibility_index(projected)
    registry = AttachmentMaterializationRegistry()
    registry.seed_from_prior_rows([_prior_row(1)], memory_config=memory_config)

    metadata = {
        "attachment_mode": "unify_lite",
        "attachments": [_prior_row(1)["metadata"]["attachments"][0]],
    }
    run_input = build_materialized_user_message(
        "@chart.png",
        metadata,
        chat_id=CHAT_ID,
        turn_sequence=3,
        registry=registry,
        visibility=visibility,
        pull_config=PUSH_PULL,
    )
    text = " ".join(getattr(c, "text", "") or "" for c in run_input.contents)
    assert ATTACHMENT_ID in text
