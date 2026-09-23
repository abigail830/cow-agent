from parse_pipeline.orchestrator.errors import job_error_from_exception


class _AliyunLikeError(Exception):
    code = None


def test_job_error_from_exception_uses_default_when_code_is_none() -> None:
    err = job_error_from_exception(_AliyunLikeError("Read timed out"), "normalize")
    assert err.code == "PARSE_FAILED"
    assert "Read timed out" in err.message
    assert err.stage_id == "normalize"
