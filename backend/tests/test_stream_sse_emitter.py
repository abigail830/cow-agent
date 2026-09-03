import uuid
from types import SimpleNamespace

from app.services.chat_run import _StreamSseEmitter


def _content(type_: str, **kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(type=type_, **kwargs)


def _update(*contents: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(contents=list(contents))


def test_reasoning_done_when_tool_call_follows():
    chat_id = uuid.uuid4()
    emitter = _StreamSseEmitter(chat_id)

    reasoning_events = emitter.emit(_update(_content("text_reasoning", text="thinking...")))
    assert [e["event"] for e in reasoning_events] == ["reasoning"]

    tool_events = emitter.emit(
        _update(_content("function_call", call_id="c1", name="postgres_run_query", arguments={"sql": "select 1"}))
    )
    assert [e["event"] for e in tool_events] == ["reasoning_done", "tool_call"]


def test_reasoning_done_on_flush():
    chat_id = uuid.uuid4()
    emitter = _StreamSseEmitter(chat_id)
    emitter.emit(_update(_content("text_reasoning", text="only reasoning")))
    flushed = emitter.flush()
    assert flushed == [{"event": "reasoning_done", "data": {"chat_id": str(chat_id)}}]
