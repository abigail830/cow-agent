import uuid
from unittest.mock import AsyncMock

from app.platform.chat.run_service import _StreamTurnAccumulator
from app.agent_specific.viz.spec import VizSpec


async def test_persist_ui_annotations_keeps_viz_rows():
    turn_id = uuid.uuid4()
    acc = _StreamTurnAccumulator(turn_id=turn_id)
    spec = VizSpec(kind="table", title="sessions by week_start", rows=[{"a": 1}])
    acc.record_viz(spec)

    repo = AsyncMock()
    repo.insert_many = AsyncMock(return_value=[object()])
    chat_id = uuid.uuid4()

    saved = await acc.persist_ui_annotations(repo, chat_id, turn_id)
    assert saved == 1
    repo.insert_many.assert_awaited_once()
    rows = repo.insert_many.await_args.args[1]
    assert rows[0]["kind"] == "viz"
    assert rows[0]["display"]["spec"]["title"] == "sessions by week_start"
