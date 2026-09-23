from __future__ import annotations

from parse_pipeline.schemas.stages import STAGE_ORDER, StageId, initial_stages


def test_initial_stages_count() -> None:
    stages = initial_stages()
    assert len(stages) == 8
    assert [s.stage_id for s in stages] == list(STAGE_ORDER)


def test_stage_ids_stable() -> None:
    assert StageId.FETCH.value == "fetch"
    assert StageId.PARSE_WAIT.value == "parse_wait"
