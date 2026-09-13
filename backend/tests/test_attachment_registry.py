import uuid

import pytest
from agent_framework import Content

from app.platform.attachments.materialization.registry import AttachmentMaterializationRegistry
from app.platform.attachments.materialization.replay import (
    build_materialized_user_message,
    build_replay_user_message_contents,
    count_image_data_blocks,
)
from app.platform.memory.maf_mapping import to_maf_messages


CHAT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ATTACHMENT_ID = "22222222-2222-2222-2222-222222222222"


def _image_attachment_meta(*, content_hash: str = "sha256:img001") -> dict:
    return {
        "id": ATTACHMENT_ID,
        "filename": "chart.png",
        "mime_type": "image/png",
        "size_bytes": 128,
        "provider": "unify_lite",
        "provider_file_id": f"inline:{ATTACHMENT_ID}",
        "content_hash": content_hash,
    }


def _user_row(*, content: str, sequence: int, attachment_meta: dict | None = None) -> dict:
    attachments = [attachment_meta or _image_attachment_meta()]
    return {
        "id": str(uuid.uuid4()),
        "chat_id": str(CHAT_ID),
        "role": "user",
        "message_type": "text",
        "content": content,
        "sequence": sequence,
        "metadata": {
            "attachment_mode": "unify_lite",
            "attachments": attachments,
        },
    }


@pytest.fixture(autouse=True)
def _mock_image_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.platform.attachments.native.maf_content.load_inline_attachment",
        lambda _chat_id, _attachment_id: b"\x89PNG\r\n",
    )


def test_registry_first_at_full_second_stub() -> None:
    prior = [_user_row(content="Analyze @chart.png", sequence=1)]
    registry = AttachmentMaterializationRegistry()
    registry.seed_from_prior_rows(prior)

    metadata = {
        "attachment_mode": "unify_lite",
        "attachments": [_image_attachment_meta()],
    }
    run_input = build_materialized_user_message(
        "@chart.png details?",
        metadata,
        chat_id=CHAT_ID,
        turn_sequence=3,
        registry=registry,
    )
    assert isinstance(run_input, Content) or hasattr(run_input, "contents")
    contents = run_input.contents if hasattr(run_input, "contents") else [run_input]
    assert count_image_data_blocks(contents) == 0
    assert any("Attachment reference" in (getattr(c, "text", "") or "") for c in contents)


def test_registry_replay_dedupes_three_turns() -> None:
    rows = [
        _user_row(content="Turn1 @chart.png", sequence=1),
        _user_row(content="Turn2 @chart.png", sequence=3),
        _user_row(content="Turn3 @chart.png", sequence=5),
    ]
    messages = to_maf_messages(rows)
    user_messages = [m for m in messages if m.role == "user"]
    data_blocks = [
        c
        for message in user_messages
        for c in message.contents
        if getattr(c, "type", None) == "data"
    ]
    assert len(data_blocks) == 1


def test_registry_out_of_window_refull() -> None:
    """Prior full inject not in prior_rows → current @ re-inlines image."""
    registry = AttachmentMaterializationRegistry()
    metadata = {
        "attachment_mode": "unify_lite",
        "attachments": [_image_attachment_meta()],
    }
    run_input = build_materialized_user_message(
        "@chart.png again",
        metadata,
        chat_id=CHAT_ID,
        turn_sequence=99,
        registry=registry,
    )
    assert count_image_data_blocks(run_input.contents) == 1


def test_registry_hash_change_rematerialize() -> None:
    prior = [
        _user_row(
            content="@chart.png",
            sequence=1,
            attachment_meta=_image_attachment_meta(content_hash="sha256:old"),
        )
    ]
    registry = AttachmentMaterializationRegistry()
    registry.seed_from_prior_rows(prior)

    metadata = {
        "attachment_mode": "unify_lite",
        "attachments": [_image_attachment_meta(content_hash="sha256:new")],
    }
    contents = build_replay_user_message_contents(
        _user_row(
            content="@chart.png v2",
            sequence=3,
            attachment_meta=_image_attachment_meta(content_hash="sha256:new"),
        ),
        registry=registry,
    )
    assert count_image_data_blocks(contents) == 1
