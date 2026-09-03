from app.memory.turn_window import group_messages_into_turns, take_last_turns


def _user(seq: int, content: str = "hi") -> dict:
    return {"role": "user", "message_type": "text", "content": content, "sequence": seq}


def _assistant(seq: int, content: str = "ok") -> dict:
    return {"role": "assistant", "message_type": "text", "content": content, "sequence": seq}


def test_group_messages_into_turns():
    rows = [_user(1), _assistant(2), _user(3), _assistant(4)]
    turns = group_messages_into_turns(rows)
    assert len(turns) == 2
    assert [r["sequence"] for r in turns[0]] == [1, 2]
    assert [r["sequence"] for r in turns[1]] == [3, 4]


def test_take_last_turns_keeps_atomic_turns():
    rows = [
        _user(1, "a"),
        _assistant(2, "b"),
        _user(3, "c"),
        _assistant(4, "d"),
        _user(5, "e"),
        _assistant(6, "f"),
    ]
    trimmed = take_last_turns(rows, 2)
    assert [r["sequence"] for r in trimmed] == [3, 4, 5, 6]
