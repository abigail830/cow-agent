from types import SimpleNamespace
from uuid import uuid4

from app.services.chat_run import _StreamSseEmitter, _merge_tool_arguments, _normalize_tool_arguments


def _content(type_: str, **kwargs):
    return SimpleNamespace(type=type_, **kwargs)


def _update(*contents):
    return SimpleNamespace(contents=list(contents))


def test_normalize_tool_arguments_parses_json_string():
    assert _normalize_tool_arguments('{"sql": "select 1"}') == {"sql": "select 1"}


def test_merge_tool_arguments_prefers_richer_payload():
    empty = {}
    full = {"sql": "select * from users where created_at >= current_date - interval '1 day'"}
    assert _merge_tool_arguments(empty, full) == full
    assert _merge_tool_arguments(full, empty) == full


def test_stream_emitter_updates_tool_call_arguments():
    emitter = _StreamSseEmitter(uuid4())
    first = emitter.emit(
        _update(
            _content(
                "function_call",
                call_id="c1",
                name="postgres_query_data",
                arguments={},
            )
        )
    )
    second = emitter.emit(
        _update(
            _content(
                "function_call",
                call_id="c1",
                name="postgres_query_data",
                arguments={"sql": "select 1"},
            )
        )
    )

    assert first[0]["event"] == "tool_call"
    assert first[0]["data"]["arguments"] == {}
    assert second[0]["event"] == "tool_call"
    assert second[0]["data"]["arguments"] == {"sql": "select 1"}


def test_stream_emitter_tool_result_includes_arguments():
    emitter = _StreamSseEmitter(uuid4())
    emitter.emit(
        _update(
            _content(
                "function_call",
                call_id="c2",
                name="patch_proposal_draft",
                arguments={
                    "patch": [
                        {"op": "replace", "path": "/facts/client/company_name", "value": "Acme"}
                    ]
                },
            )
        )
    )
    events = emitter.emit(
        _update(
            _content(
                "function_result",
                call_id="c2",
                result="Error: Argument parsing failed.",
            )
        )
    )

    assert len(events) == 1
    assert events[0]["event"] == "tool_result"
    assert events[0]["data"]["arguments"] == {
        "patch": [{"op": "replace", "path": "/facts/client/company_name", "value": "Acme"}],
    }
    assert events[0]["data"]["result"] == "Error: Argument parsing failed."
