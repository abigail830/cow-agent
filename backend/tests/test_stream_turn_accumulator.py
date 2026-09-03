from types import SimpleNamespace

from app.services.chat_run import _StreamTurnAccumulator


def _reasoning_update(text: str) -> SimpleNamespace:
    return SimpleNamespace(contents=[SimpleNamespace(type="text_reasoning", text=text)])


def test_reasoning_cumulative_chunks_do_not_duplicate():
    acc = _StreamTurnAccumulator()
    acc.observe(_reasoning_update("step one"))
    acc.observe(_reasoning_update("step one and two"))
    acc.finalize()
    reasoning = [r for r in acc._rows if r["message_type"] == "reasoning"]
    assert len(reasoning) == 1
    assert reasoning[0]["content"] == "step one and two"


def test_reasoning_segments_flush_separately():
    acc = _StreamTurnAccumulator()
    acc.observe(_reasoning_update("first segment"))
    acc.observe(SimpleNamespace(contents=[SimpleNamespace(type="function_call", call_id="c1", name="tool", arguments={})]))
    acc.observe(_reasoning_update("second segment"))
    acc.finalize()
    reasoning = [r["message_type"] for r in acc._rows]
    assert reasoning.count("reasoning") == 2


def test_text_duplicating_reasoning_is_dropped():
    acc = _StreamTurnAccumulator()
    acc.observe(_reasoning_update("internal plan only"))
    acc.observe(SimpleNamespace(contents=[SimpleNamespace(type="text", text="internal plan only")]))
    acc.finalize()
    types = [r["message_type"] for r in acc._rows]
    assert types == ["reasoning"]
