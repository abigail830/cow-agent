"""SessionStore finalize_turn incremental working-set merge and payload overlay."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.platform.memory.memory_config import MemoryConfig
from app.platform.session.session_store import SessionStore, WORKING_SET_VERSION


@pytest.mark.asyncio
async def test_finalize_turn_merges_rows_without_full_db_scan():
    chat_id = uuid.uuid4()
    db = AsyncMock()
    store = SessionStore(db)
    memory_config = MemoryConfig()

    existing_payload = {
        "session": {"session_id": str(chat_id), "type": "session"},
        "working_set": {
            "version": WORKING_SET_VERSION,
            "config_hash": memory_config.config_hash(),
            "last_sequence": 2,
            "rows": [
                {"sequence": 1, "role": "user", "message_type": "text", "content": "hi", "metadata": {}},
                {"sequence": 2, "role": "assistant", "message_type": "text", "content": "hello", "metadata": {}},
            ],
        },
    }
    session = MagicMock()
    session.to_dict.return_value = {"session_id": str(chat_id), "type": "session", "updated": True}

    store._load_payload = AsyncMock(return_value=dict(existing_payload))
    store._save_payload = AsyncMock()

    turn_rows = [
        {"sequence": 3, "role": "user", "message_type": "text", "content": "next", "metadata": {}},
        {"sequence": 4, "role": "assistant", "message_type": "text", "content": "reply", "metadata": {}},
    ]

    await store.finalize_turn(chat_id, session, memory_config, turn_rows)

    store._save_payload.assert_awaited_once()
    saved_payload = store._save_payload.await_args.args[1]
    assert saved_payload["session"]["updated"] is True
    rows = saved_payload["working_set"]["rows"]
    assert [row["sequence"] for row in rows] == [1, 2, 3, 4]


@pytest.mark.asyncio
async def test_load_payload_db_overlays_non_core_keys_onto_redis():
    chat_id = uuid.uuid4()
    store = SessionStore(AsyncMock())
    store._load_payload_from_db = AsyncMock(
        return_value={
            "session": {"session_id": "db", "type": "session"},
            "working_set": {"version": WORKING_SET_VERSION, "rows": []},
            "proposal_draft": {"version": 1, "meta": {"template_id": "bvi"}},
            "fulfillment_forms": {"forms": [{"form_id": "f1"}]},
        }
    )
    store._get_from_redis = AsyncMock(
        return_value={
            "session": {"session_id": "redis", "type": "session"},
            "working_set": {"version": WORKING_SET_VERSION, "rows": [{"sequence": 1}]},
            "proposal_draft": {},
            "fulfillment_forms": {"forms": []},
        }
    )

    payload = await store._load_payload(chat_id)

    assert payload["session"]["session_id"] == "redis"
    assert payload["working_set"]["rows"] == [{"sequence": 1}]
    assert payload["proposal_draft"]["meta"]["template_id"] == "bvi"
    assert payload["fulfillment_forms"]["forms"] == [{"form_id": "f1"}]


@pytest.mark.asyncio
async def test_load_payload_does_not_invent_extension_keys():
    chat_id = uuid.uuid4()
    store = SessionStore(AsyncMock())
    store._load_payload_from_db = AsyncMock(
        return_value={
            "session": {"session_id": "db", "type": "session"},
            "working_set": {"version": WORKING_SET_VERSION, "rows": []},
        }
    )
    store._get_from_redis = AsyncMock(
        return_value={
            "session": {"session_id": "redis", "type": "session"},
            "working_set": {"version": WORKING_SET_VERSION, "rows": []},
        }
    )

    payload = await store._load_payload(chat_id)

    assert "proposal_draft" not in payload
    assert "fulfillment_forms" not in payload
