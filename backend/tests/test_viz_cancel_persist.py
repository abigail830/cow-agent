import uuid
from unittest.mock import AsyncMock

from app.platform.chat.run_service import _StreamTurnAccumulator
from app.agent_specific.viz.spec import VizSpec


async def test_persist_cancelled_keeps_viz_rows():
    acc = _StreamTurnAccumulator()
    spec = VizSpec(kind="table", title="sessions by week_start", rows=[{"a": 1}])
    acc.record_viz(spec)

    repo = AsyncMock()
    repo.insert_many = AsyncMock(return_value=[object()])
    chat_id = uuid.uuid4()
    run_id = uuid.uuid4()

    saved = await acc.persist_cancelled(repo, chat_id, run_id)
    assert saved == 1
    repo.insert_many.assert_awaited_once()
    rows = repo.insert_many.await_args.args[1]
    assert rows[0]["message_type"] == "viz"
    assert rows[0]["metadata"]["spec"]["title"] == "sessions by week_start"
