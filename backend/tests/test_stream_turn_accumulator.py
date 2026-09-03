import uuid
from types import SimpleNamespace

import pytest

from app.services.chat_run import _StreamTurnAccumulator


def _content(type_: str, **kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(type=type_, **kwargs)


def _update(*contents: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(contents=list(contents))


def test_accumulator_persists_reasoning_tool_and_text():
    acc = _StreamTurnAccumulator()
    acc.observe(_update(_content("text_reasoning", text="plan")))
    acc.observe(
        _update(
            _content(
                "function_call",
                call_id="c1",
                name="search_docs",
                arguments={"q": "policy"},
            )
        )
    )
    acc.observe(_update(_content("function_result", call_id="c1", result='{"hits": 1}')))
    acc.observe(_update(_content("text_reasoning", text=" summarize")))
    acc.observe(_update(_content("text", text="Final answer")))
    acc.finalize()

    assert len(acc._rows) == 5
    assert acc._rows[0]["message_type"] == "reasoning"
    assert acc._rows[0]["content"] == "plan"
    assert acc._rows[1]["message_type"] == "tool_call"
    assert acc._rows[2]["message_type"] == "tool_result"
    assert acc._rows[3]["message_type"] == "reasoning"
    assert acc._rows[3]["content"] == " summarize"
    assert acc._rows[4]["message_type"] == "text"
    assert acc._rows[4]["content"] == "Final answer"


def test_accumulator_merges_cumulative_text_chunks():
    acc = _StreamTurnAccumulator()
    acc.observe(_update(_content("text", text="Hel")))
    acc.observe(_update(_content("text", text="Hello")))
    acc.observe(_update(_content("text", text="Hello world")))
    acc.finalize()

    assert len(acc._rows) == 1
    assert acc._rows[0]["content"] == "Hello world"


@pytest.mark.asyncio
async def test_accumulator_persist_calls_repo():
    acc = _StreamTurnAccumulator()
    acc.observe(_update(_content("text", text="partial")))

    inserted: list[dict] = []

    class FakeRepo:
        async def insert(self, **kwargs: object) -> None:
            inserted.append(kwargs)

    await acc.persist(FakeRepo(), uuid.uuid4())
    assert len(inserted) == 1
    assert inserted[0]["message_type"] == "text"
    assert inserted[0]["content"] == "partial"


@pytest.mark.asyncio
async def test_accumulator_persist_keeps_reasoning_tools_before_text():
    acc = _StreamTurnAccumulator()
    acc.observe(_update(_content("text_reasoning", text="plan")))
    acc.observe(
        _update(
            _content(
                "function_call",
                call_id="c1",
                name="load_skill",
                arguments={"skill_name": "topic-daily-analysis"},
            )
        )
    )
    acc.observe(_update(_content("function_result", call_id="c1", result="ok")))
    acc.observe(_update(_content("text", text="Final answer")))

    inserted: list[dict] = []
    seq = 0

    class FakeRepo:
        async def insert(self, **kwargs: object) -> None:
            nonlocal seq
            seq += 1
            inserted.append({**kwargs, "sequence": seq})

    await acc.persist(FakeRepo(), uuid.uuid4())
    assert [row["message_type"] for row in inserted] == [
        "reasoning",
        "tool_call",
        "tool_result",
        "text",
    ]
    assert [row["sequence"] for row in inserted] == [1, 2, 3, 4]
