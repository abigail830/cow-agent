from unittest.mock import patch
from types import SimpleNamespace
import json

from app.agent_specific.proposal.draft import build_draft_preview
from app.agent_specific.proposal.preview import proposal_state_fingerprint


def test_fingerprint_changes_when_draft_changes():
    draft = {"facts": {"client": {"company_name": "Demo Ltd"}}}
    fp1 = proposal_state_fingerprint(draft)
    draft["facts"]["client"]["company_name"] = "Acme Ltd"
    fp2 = proposal_state_fingerprint(draft)
    assert fp1 != fp2


def test_build_draft_preview_empty_draft():
    preview = build_draft_preview({})
    assert preview["status"] == "empty"
    assert preview["markdown"] == ""
    assert preview["export"]["word"]["available"] is False


def test_build_draft_preview_includes_harneys_word_export():
    from app.agent_specific.proposal.draft import materialize_draft

    draft = materialize_draft(template_id="harneys-bvi")
    preview = build_draft_preview(draft)
    assert preview["export"]["word"]["available"] is True
    assert preview["export"]["word"]["template_file"] == "proposal.docx"


def test_get_chat_proposal_draft_returns_persisted_draft():
    import asyncio
    import uuid

    from app.agent_specific.proposal.preview_service import get_chat_proposal_draft

    draft = {
        "meta": {"template_id": "au-advisory"},
        "facts": {"client": {"company_name": "Demo Ltd"}},
        "document": {"sections": []},
    }

    async def _run():
        with patch(
            "app.agent_specific.proposal.draft.preview_service.load_chat_proposal_draft",
            return_value=draft,
        ):
            return await get_chat_proposal_draft(None, uuid.uuid4())

    payload = asyncio.run(_run())
    assert payload["draft"]["facts"]["client"]["company_name"] == "Demo Ltd"
    assert payload["state_fingerprint"]


def test_recover_proposal_draft_from_latest_draft_tool_result():
    import asyncio
    import uuid

    from app.agent_specific.proposal.preview_service import _recover_proposal_draft_from_messages

    old_draft = {"facts": {"client": {"company_name": "Old Ltd"}}}
    latest_draft = {"facts": {"client": {"company_name": "Latest Ltd"}}}
    events = [
        SimpleNamespace(
            id=uuid.uuid4(),
            chat_id=uuid.uuid4(),
            sequence=1,
            event_type="message",
            payload={
                "role": "tool",
                "message_type": "tool_result",
                "metadata": {
                    "tool_name": "initialize_proposal_draft",
                    "result": {"status": "ok", "draft": old_draft},
                },
            },
            created_at=None,
        ),
        SimpleNamespace(
            id=uuid.uuid4(),
            chat_id=uuid.uuid4(),
            sequence=2,
            event_type="message",
            payload={
                "role": "tool",
                "message_type": "tool_result",
                "metadata": {
                    "tool_name": "patch_proposal_draft",
                    "result": json.dumps({"status": "ok", "draft": latest_draft}),
                },
            },
            created_at=None,
        ),
    ]

    class FakeRepo:
        def __init__(self, _db):
            pass

        async def list_by_chat(self, _chat_id):
            return events

    async def _run():
        with patch("app.agent_specific.proposal.draft.preview_service.ChatEventRepository", FakeRepo):
            return await _recover_proposal_draft_from_messages(None, uuid.uuid4())

    recovered = asyncio.run(_run())
    assert recovered == latest_draft
