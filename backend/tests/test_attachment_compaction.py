import uuid

import pytest

from app.platform.attachments.materialization.compaction import strip_attachment_heavy_payload
from app.platform.attachments.materialization.replay import build_materialized_user_message
from app.platform.attachments.materialization.registry import AttachmentMaterializationRegistry
from app.platform.attachments.materialization.replay import count_image_data_blocks
from app.platform.memory.maf_mapping import to_maf_messages
from app.platform.memory.memory_config import parse_memory_config
from app.platform.memory.slimmer import HistoryProjection


CHAT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ATTACHMENT_ID = "22222222-2222-2222-2222-222222222222"


def _image_user_row(sequence: int) -> dict:
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
                    "extracted_snapshot": {
                        "content_hash": "sha256:img001",
                        "text": "",
                        "truncated": False,
                        "char_count": 0,
                    },
                }
            ],
        },
    }


def test_compaction_strips_image_data_from_old_turn() -> None:
    row = _image_user_row(1)
    row["metadata"]["attachments"][0]["extracted_snapshot"]["text"] = "Full document body"
    stripped = strip_attachment_heavy_payload(row)
    att = stripped["metadata"]["attachments"][0]
    assert att.get("compaction_placeholder") is True
    assert "compacted" in att.get("extracted_snapshot", {}).get("text", "").lower() or "移除" in att.get(
        "extracted_snapshot", {}
    ).get("text", "")


def test_history_projection_strips_old_user_attachments() -> None:
    cfg = parse_memory_config({"memory": {"slim": {"enabled": True}}})
    projection = HistoryProjection()
    rows = []
    for seq in (1, 3, 5, 7):
        row = _image_user_row(seq)
        row["metadata"]["attachments"][0]["extracted_snapshot"]["text"] = f"Body turn {seq}"
        rows.append(row)
    projected = projection.project_rows(rows, cfg)[0]
    assert projected["metadata"]["attachments"][0].get("compaction_placeholder") is True


@pytest.fixture(autouse=True)
def _mock_image_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.platform.attachments.native.maf_content.load_inline_attachment",
        lambda _chat_id, _attachment_id: b"\x89PNG\r\n",
    )


def test_after_compaction_re_at_reinlines() -> None:
    row = strip_attachment_heavy_payload(_image_user_row(1))
    registry = AttachmentMaterializationRegistry()
    registry.seed_from_prior_rows([row])

    metadata = {
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
    }
    run_input = build_materialized_user_message(
        "@chart.png again after compaction",
        metadata,
        chat_id=CHAT_ID,
        turn_sequence=5,
        registry=registry,
    )
    assert count_image_data_blocks(run_input.contents) == 1


def test_compacted_replay_no_image_data_block() -> None:
    row = strip_attachment_heavy_payload(_image_user_row(1))
    messages = to_maf_messages([row])
    data_blocks = [
        c for m in messages for c in m.contents if getattr(c, "type", None) == "data"
    ]
    assert len(data_blocks) == 0
