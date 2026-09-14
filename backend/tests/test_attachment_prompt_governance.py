"""Prompt/code alignment for attachment visibility vocabulary."""

from __future__ import annotations

from app.platform.agent import platform_instructions
from app.platform.attachments.tools import pull_tools
from app.platform.attachments.visibility_constants import (
    ALL_VISIBILITY_STATES,
    ANALYZE_IMAGE_TOOL_DESCRIPTION,
    ATTACHMENT_PLATFORM_INSTRUCTIONS_BODY,
    GUARD_ALREADY_INLINED_MESSAGE,
    GUARD_JUST_INLINED_MESSAGE,
    INLINE_ATTACHMENT_TOOL_DESCRIPTION,
)
from app.platform.attachments.tools.pull_tools import _visibility_guard


def test_all_visibility_states_in_platform_instructions() -> None:
    body = platform_instructions._ATTACHMENT_PULL_INSTRUCTIONS
    for state in ALL_VISIBILITY_STATES:
        assert state in body, f"missing visibility state {state!r} in platform instructions"


def test_tool_descriptions_reference_visibility_states_they_gate() -> None:
    assert "visibility=not_inlined" in INLINE_ATTACHMENT_TOOL_DESCRIPTION
    assert "visibility=inlined_this_turn" in INLINE_ATTACHMENT_TOOL_DESCRIPTION
    assert "visibility=not_inlined" in ANALYZE_IMAGE_TOOL_DESCRIPTION
    assert "visibility=inlined_this_turn" in ANALYZE_IMAGE_TOOL_DESCRIPTION


def test_guard_messages_reference_inlined_state_and_recovery_hint() -> None:
    assert "visibility=inlined_this_turn" in GUARD_ALREADY_INLINED_MESSAGE
    assert "Answer directly" in GUARD_ALREADY_INLINED_MESSAGE
    assert "do not retry" in GUARD_ALREADY_INLINED_MESSAGE.lower()


def test_visibility_guard_returns_recovery_field_when_blocked() -> None:
    from app.platform.attachments.run_state import AttachmentRecord, init_attachment_run_state, reset_attachment_run_state
    import uuid

    reset_attachment_run_state()
    chat_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    att_id = "22222222-2222-2222-2222-222222222222"
    state = init_attachment_run_state(
        chat_id=chat_id,
        attachments=[
            AttachmentRecord(
                attachment_id=uuid.UUID(att_id),
                chat_id=chat_id,
                filename="x.png",
                mime_type="image/png",
                provider="unify_lite",
                provider_file_id=f"inline:{att_id}",
                size_bytes=1,
            )
        ],
    )
    state.turn_visibility[att_id] = "inlined_this_turn"

    blocked = _visibility_guard(att_id)
    assert blocked is not None
    assert blocked["status"] == "error"
    assert blocked.get("recovery") == "answer_from_context"
    assert "Answer directly" in blocked["message"]

    reset_attachment_run_state()


def test_platform_instructions_use_canonical_body() -> None:
    assert ATTACHMENT_PLATFORM_INSTRUCTIONS_BODY in platform_instructions._ATTACHMENT_PULL_INSTRUCTIONS


def test_platform_instructions_can_omit_attachment_pull() -> None:
    with_pull = platform_instructions.append_platform_instructions("You are a helper.")
    without_pull = platform_instructions.append_platform_instructions(
        "You are a helper.",
        include_attachment_pull=False,
    )
    assert ATTACHMENT_PLATFORM_INSTRUCTIONS_BODY in with_pull
    assert ATTACHMENT_PLATFORM_INSTRUCTIONS_BODY not in without_pull
    assert "analyze_image" not in without_pull


def test_pull_tools_import_canonical_descriptions() -> None:
    assert pull_tools.INLINE_ATTACHMENT_TOOL_DESCRIPTION == INLINE_ATTACHMENT_TOOL_DESCRIPTION
    assert pull_tools.ANALYZE_IMAGE_TOOL_DESCRIPTION == ANALYZE_IMAGE_TOOL_DESCRIPTION
