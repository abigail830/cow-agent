from agent_framework import Content, Message

from app.memory.maf_mapping import maf_message_to_rows, to_maf_messages


def test_reasoning_round_trip_preserves_thinking_signature():
    message = Message(
        role="assistant",
        contents=[
            Content.from_text_reasoning(
                text="Let me analyze the hot topics.",
                id="reasoning-1",
                protected_data="sig_abc123",
            )
        ],
    )

    rows = maf_message_to_rows("chat-1", message, start_sequence=1)
    assert len(rows) == 1
    assert rows[0]["message_type"] == "reasoning"
    assert rows[0]["metadata"]["protected_data"] == "sig_abc123"
    assert rows[0]["metadata"]["content_id"] == "reasoning-1"

    rebuilt = to_maf_messages(rows)
    assert len(rebuilt) == 1
    reasoning = rebuilt[0].contents[0]
    assert reasoning.type == "text_reasoning"
    assert reasoning.text == "Let me analyze the hot topics."
    assert reasoning.protected_data == "sig_abc123"
    assert reasoning.id == "reasoning-1"
