import uuid

from agent_framework import Content, Message

from app.db.models import ChatMessage
from app.platform.chat.timeline_projection import build_turn_message_outs, expand_message_to_platform_rows


def test_expand_message_to_platform_rows():
    message = ChatMessage(
        id=uuid.uuid4(),
        chat_id=uuid.uuid4(),
        sequence=3,
        turn_id=uuid.uuid4(),
        run_id=None,
        role="assistant",
        maf_message_id=None,
        body=Message(
            role="assistant",
            contents=[Content.from_text("Hi there")],
        ).to_dict(),
    )
    rows = expand_message_to_platform_rows(message)
    assert len(rows) == 1
    assert rows[0]["message_type"] == "text"
    assert rows[0]["content"] == "Hi there"
    assert rows[0]["sequence"] == 300


def test_build_turn_message_outs_includes_user_and_assistant():
    chat_id = uuid.uuid4()
    turn_id = uuid.uuid4()
    user = ChatMessage(
        id=uuid.uuid4(),
        chat_id=chat_id,
        sequence=1,
        turn_id=turn_id,
        run_id=None,
        role="user",
        maf_message_id=None,
        body=Message(role="user", contents=[Content.from_text("Q")]).to_dict(),
    )
    assistant = ChatMessage(
        id=uuid.uuid4(),
        chat_id=chat_id,
        sequence=2,
        turn_id=turn_id,
        run_id=None,
        role="assistant",
        maf_message_id=None,
        body=Message(role="assistant", contents=[Content.from_text("A")]).to_dict(),
    )
    outs = build_turn_message_outs(chat_id, user, [assistant])
    assert len(outs) == 2
    assert outs[0]["role"] == "user"
    assert outs[1]["role"] == "assistant"
