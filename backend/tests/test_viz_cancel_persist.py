import uuid
from unittest.mock import AsyncMock

from app.services.chat_run import _StreamTurnAccumulator
from app.viz.spec import VizSpec


async def test_persist_cancelled_keeps_viz_rows():
    acc = _StreamTurnAccumulator()
    spec = VizSpec(kind="table", title="sessions by week_start", rows=[{"a": 1}])
    acc.record_viz(spec)

    repo = AsyncMock()
    repo.insert = AsyncMock()
    chat_id = uuid.uuid4()
    run_id = uuid.uuid4()

    saved = await acc.persist_cancelled(repo, chat_id, run_id)
    assert saved == 1
    repo.insert.assert_awaited_once()
    kwargs = repo.insert.await_args.kwargs
    assert kwargs["message_type"] == "viz"
    assert kwargs["metadata"]["spec"]["title"] == "sessions by week_start"
