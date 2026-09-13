"""Working set must retain user rows (with attachment metadata) for multi-turn replay."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.platform.chat.run_service import _working_set_rows_for_finalize
from app.platform.memory.maf_mapping import to_maf_messages
from app.platform.memory.memory_config import MemoryConfig
from app.platform.session.session_store import SessionStore, WORKING_SET_VERSION


class _UserRow:
    def __init__(self) -> None:
        self.id = uuid.uuid4()
        self.chat_id = uuid.uuid4()
        self.role = "user"
        self.content = "请总结 @report.docx"
        self.message_type = "text"
        self.message_metadata = {
            "attachment_mode": "unify_lite",
            "attachments": [
                {
                    "id": str(uuid.uuid4()),
                    "filename": "report.docx",
                    "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    "size_bytes": 100,
                    "provider": "unify_lite",
                    "provider_file_id": "inline:test",
                    "extracted_snapshot": {
                        "content_hash": "sha256:abc",
                        "text": "Revenue grew 12%.",
                        "truncated": False,
                        "char_count": 18,
                    },
                }
            ],
        }
        self.parent_id = None
        self.sequence = 1


def test_working_set_rows_for_finalize_includes_user_row() -> None:
    user_row = _UserRow()
    assistant_rows = [
        {"sequence": 2, "role": "assistant", "message_type": "text", "content": "summary", "metadata": {}},
    ]
    merged = _working_set_rows_for_finalize(user_row, assistant_rows)
    assert merged[0]["sequence"] == 1
    assert merged[0]["metadata"]["attachments"][0]["extracted_snapshot"]["text"] == "Revenue grew 12%."
    assert merged[1]["sequence"] == 2


@pytest.mark.asyncio
async def test_finalize_turn_keeps_user_attachment_metadata_in_working_set() -> None:
    chat_id = uuid.uuid4()
    store = SessionStore(AsyncMock())
    memory_config = MemoryConfig()
    session = MagicMock()
    session.to_dict.return_value = {"session_id": str(chat_id), "type": "session"}

    user_row = _UserRow()
    user_row.chat_id = chat_id
    user_dict = {
        "id": str(user_row.id),
        "chat_id": str(chat_id),
        "role": "user",
        "message_type": "text",
        "content": user_row.content,
        "metadata": user_row.message_metadata,
        "sequence": 1,
    }
    assistant_row = {
        "sequence": 2,
        "role": "assistant",
        "message_type": "text",
        "content": "Done.",
        "metadata": {},
    }

    store._load_payload = AsyncMock(
        return_value={
            "session": session.to_dict(),
            "working_set": {
                "version": WORKING_SET_VERSION,
                "config_hash": memory_config.config_hash(),
                "last_sequence": 0,
                "rows": [],
            },
        }
    )
    store._save_payload = AsyncMock()

    await store.finalize_turn(chat_id, session, memory_config, [user_dict, assistant_row])

    saved = store._save_payload.await_args.args[1]
    rows = saved["working_set"]["rows"]
    assert rows[0]["metadata"]["attachments"][0]["extracted_snapshot"]["text"] == "Revenue grew 12%."


def test_working_set_history_replays_attachment_on_follow_up_turn() -> None:
    chat_id = str(uuid.uuid4())
    attachment_id = str(uuid.uuid4())
    rows = [
        {
            "id": str(uuid.uuid4()),
            "chat_id": chat_id,
            "role": "user",
            "message_type": "text",
            "content": "请总结 @report.docx",
            "sequence": 1,
            "metadata": {
                "attachment_mode": "unify_lite",
                "attachments": [
                    {
                        "id": attachment_id,
                        "filename": "report.docx",
                        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        "size_bytes": 100,
                        "provider": "unify_lite",
                        "provider_file_id": f"inline:{attachment_id}",
                        "extracted_snapshot": {
                            "content_hash": "sha256:abc",
                            "text": "Revenue grew 12%.",
                            "truncated": False,
                            "char_count": 18,
                        },
                    }
                ],
            },
        },
        {
            "id": str(uuid.uuid4()),
            "chat_id": chat_id,
            "role": "assistant",
            "message_type": "text",
            "content": "Revenue grew 12%.",
            "sequence": 2,
            "metadata": {},
        },
        {
            "id": str(uuid.uuid4()),
            "chat_id": chat_id,
            "role": "user",
            "message_type": "text",
            "content": "刚才文档里的数字是多少？",
            "sequence": 3,
            "metadata": {},
        },
    ]

    history_rows = [row for row in rows if int(row["sequence"]) < 3]
    messages = to_maf_messages(history_rows)
    all_text = " ".join(
        getattr(content, "text", "") or ""
        for message in messages
        for content in message.contents
    )
    assert "Revenue grew 12%" in all_text
