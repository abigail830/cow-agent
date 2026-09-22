"""SessionStore finalize_run and payload merge behavior."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.platform.session.session_store import SessionStore


@pytest.mark.asyncio
async def test_finalize_run_persists_session_and_extensions():
    chat_id = uuid.uuid4()
    store = SessionStore(AsyncMock())
    session = MagicMock()
    session.to_dict.return_value = {"session_id": str(chat_id), "type": "session", "updated": True}

    store._load_payload = AsyncMock(return_value={"proposal_draft": {"version": 1}})
    store._save_payload = AsyncMock()

    await store.finalize_run(
        chat_id,
        session,
        payload_extensions={"fulfillment_forms": {"forms": []}},
    )

    store._save_payload.assert_awaited_once()
    saved_payload = store._save_payload.await_args.args[1]
    assert saved_payload["session"]["updated"] is True
    assert saved_payload["fulfillment_forms"] == {"forms": []}
    assert saved_payload["proposal_draft"] == {"version": 1}


@pytest.mark.asyncio
async def test_load_payload_db_overlays_non_core_keys_onto_redis():
    chat_id = uuid.uuid4()
    store = SessionStore(AsyncMock())
    store._load_payload_from_db = AsyncMock(
        return_value={
            "session": {"session_id": "db", "type": "session"},
            "proposal_draft": {"version": 1, "meta": {"template_id": "bvi"}},
            "fulfillment_forms": {"forms": [{"form_id": "f1"}]},
        }
    )
    store._get_from_redis = AsyncMock(
        return_value={
            "session": {"session_id": "redis", "type": "session"},
            "proposal_draft": {},
            "fulfillment_forms": {"forms": []},
        }
    )

    payload = await store._load_payload(chat_id)

    assert payload["session"]["session_id"] == "redis"
    assert payload["proposal_draft"]["meta"]["template_id"] == "bvi"
    assert payload["fulfillment_forms"]["forms"] == [{"form_id": "f1"}]


@pytest.mark.asyncio
async def test_load_payload_does_not_invent_extension_keys():
    chat_id = uuid.uuid4()
    store = SessionStore(AsyncMock())
    store._load_payload_from_db = AsyncMock(
        return_value={"session": {"session_id": "db", "type": "session"}}
    )
    store._get_from_redis = AsyncMock(
        return_value={"session": {"session_id": "redis", "type": "session"}}
    )

    payload = await store._load_payload(chat_id)

    assert "proposal_draft" not in payload
    assert "fulfillment_forms" not in payload
