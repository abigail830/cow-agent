import uuid

import pytest
from agent_framework import Content, Message

from app.db.models import ChatMessage, ChatRun, ChatUiAnnotation
from app.platform.chat.timeline_projection import (
    expand_message_to_platform_rows,
    merge_timeline_to_message_outs,
)


def test_expand_message_assigns_sub_sequences():
    message = ChatMessage(
        id=uuid.uuid4(),
        chat_id=uuid.uuid4(),
        sequence=2,
        turn_id=uuid.uuid4(),
        run_id=None,
        role="assistant",
        maf_message_id=None,
        body=Message(
            role="assistant",
            contents=[
                Content.from_text_reasoning(text="think"),
                Content.from_text("answer"),
            ],
        ).to_dict(),
    )
    rows = expand_message_to_platform_rows(message)
    assert len(rows) == 2
    assert rows[0]["sequence"] == 200
    assert rows[1]["sequence"] == 201
    assert rows[0]["message_type"] == "reasoning"
    assert rows[1]["message_type"] == "text"


def test_merge_timeline_inserts_run_markers_from_runs_table():
    chat_id = uuid.uuid4()
    turn_id = uuid.uuid4()
    user_id = uuid.uuid4()
    user = ChatMessage(
        id=user_id,
        chat_id=chat_id,
        sequence=1,
        turn_id=turn_id,
        run_id=None,
        role="user",
        maf_message_id=None,
        body=Message(role="user", contents=[Content.from_text("hi")]).to_dict(),
    )
    run = ChatRun(
        id=uuid.uuid4(),
        chat_id=chat_id,
        user_message_id=user_id,
        status="cancelled",
        error=None,
        model_id=None,
    )
    outs = merge_timeline_to_message_outs(
        chat_id=chat_id,
        messages=[user],
        annotations=[],
        runs=[run],
        include_run_markers=True,
    )
    assert any(row["message_type"] == "run_cancelled" for row in outs)


def test_merge_timeline_preserves_interleaved_artifact_order():
    chat_id = uuid.uuid4()
    turn_id = uuid.uuid4()
    user_id = uuid.uuid4()
    assistant_id = uuid.uuid4()
    user = ChatMessage(
        id=user_id,
        chat_id=chat_id,
        sequence=1,
        turn_id=turn_id,
        run_id=None,
        role="user",
        maf_message_id=None,
        body=Message(role="user", contents=[Content.from_text("hi")]).to_dict(),
    )
    assistant = ChatMessage(
        id=assistant_id,
        chat_id=chat_id,
        sequence=2,
        turn_id=turn_id,
        run_id=None,
        role="assistant",
        maf_message_id=None,
        body=Message(
            role="assistant",
            contents=[Content.from_text("before artifact after")],
            additional_properties={
                "platform": {
                    "ui_timeline": [
                        {"kind": "text", "content": "before", "metadata": {}},
                        {
                            "kind": "artifact",
                            "metadata": {
                                "spec": {
                                    "artifact_id": "art-1",
                                    "title": "Diagram",
                                    "kind": "diagram",
                                }
                            },
                        },
                        {"kind": "text", "content": "after", "metadata": {}},
                    ]
                }
            },
        ).to_dict(),
    )
    annotation = ChatUiAnnotation(
        id=uuid.uuid4(),
        chat_id=chat_id,
        sequence=99,
        turn_id=turn_id,
        anchor_message_id=None,
        kind="artifact",
        ref="art-1",
        display={"title": "Diagram", "spec": {"artifact_id": "art-1", "title": "Diagram"}},
    )
    outs = merge_timeline_to_message_outs(
        chat_id=chat_id,
        messages=[user, assistant],
        annotations=[annotation],
    )
    assistant_rows = [row for row in outs if row["role"] != "user"]
    assert [row["message_type"] for row in assistant_rows] == ["text", "artifact", "text"]
    assert assistant_rows[0]["content"] == "before"
    assert assistant_rows[2]["content"] == "after"
    assert assistant_rows[1]["metadata"]["spec"]["artifact_id"] == "art-1"


def test_merge_timeline_skips_run_markers_by_default():
    chat_id = uuid.uuid4()
    turn_id = uuid.uuid4()
    user_id = uuid.uuid4()
    user = ChatMessage(
        id=user_id,
        chat_id=chat_id,
        sequence=1,
        turn_id=turn_id,
        run_id=None,
        role="user",
        maf_message_id=None,
        body=Message(role="user", contents=[Content.from_text("hi")]).to_dict(),
    )
    run = ChatRun(
        id=uuid.uuid4(),
        chat_id=chat_id,
        user_message_id=user_id,
        status="cancelled",
        error=None,
        model_id=None,
    )
    outs = merge_timeline_to_message_outs(
        chat_id=chat_id,
        messages=[user],
        annotations=[],
        runs=[run],
    )
    assert not any(row["message_type"] == "run_cancelled" for row in outs)
