import uuid

import pytest

from app.runs.manager import RunManager, RunStatus


@pytest.mark.asyncio
async def test_cancel_finalizes_immediately():
    manager = RunManager()
    chat_id = uuid.uuid4()
    user_message_id = uuid.uuid4()
    run = await manager.start_run(chat_id, user_message_id)

    finalized = False

    async def finalize() -> None:
        nonlocal finalized
        finalized = True

    await manager.register_finalize(run.run_id, finalize)
    cancelled = await manager.cancel(run.run_id)

    assert cancelled is not None
    assert cancelled.stop_event.is_set()
    assert cancelled.status == RunStatus.CANCELLED
    assert finalized is True

    again = await manager.finalize_cancelled(run.run_id)
    assert again is False

    await manager.complete(run.run_id)
