from app.memory.maf_mapping import to_maf_messages
from app.platform.platform_instructions import RUN_CANCELLED_USER_TEXT


def test_run_cancelled_maps_to_user_message():
    rows = [
        {
            "id": "1",
            "chat_id": "c1",
            "role": "user",
            "content": "hello",
            "message_type": "text",
            "metadata": {},
            "parent_id": None,
            "sequence": 1,
        },
        {
            "id": "2",
            "chat_id": "c1",
            "role": "user",
            "content": RUN_CANCELLED_USER_TEXT,
            "message_type": "run_cancelled",
            "metadata": {"run_id": "r1"},
            "parent_id": None,
            "sequence": 2,
        },
    ]
    messages = to_maf_messages(rows)
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "user"
    assert messages[1].contents[0].text == RUN_CANCELLED_USER_TEXT


def test_cancelled_partial_maps_with_prefix():
    rows = [
        {
            "id": "1",
            "chat_id": "c1",
            "role": "assistant",
            "content": "draft answer",
            "message_type": "cancelled",
            "metadata": {"original_type": "text", "partial": True},
            "parent_id": None,
            "sequence": 1,
        },
        {
            "id": "2",
            "chat_id": "c1",
            "role": "assistant",
            "content": "thinking...",
            "message_type": "cancelled",
            "metadata": {"original_type": "reasoning", "partial": True},
            "parent_id": None,
            "sequence": 2,
        },
    ]
    messages = to_maf_messages(rows)
    assert len(messages) == 1
    assert messages[0].contents[0].text == "[Cancelled partial response] draft answer"
    assert messages[0].contents[1].type == "text"
    assert "thinking..." in messages[0].contents[1].text


def test_reasoning_without_signature_replays_as_text():
    rows = [
        {
            "id": "1",
            "chat_id": "c1",
            "role": "assistant",
            "content": "internal thought",
            "message_type": "reasoning",
            "metadata": {},
            "parent_id": None,
            "sequence": 1,
        },
    ]
    messages = to_maf_messages(rows)
    assert len(messages) == 1
    assert messages[0].contents[0].type == "text"
    assert messages[0].contents[0].text == "internal thought"
