from __future__ import annotations

from parse_pipeline.schemas.job import JobError


def job_error_from_exception(exc: Exception, stage_id: str | None) -> JobError:
    raw_code = getattr(exc, "code", None)
    code = str(raw_code).strip() if raw_code is not None else ""
    if not code:
        code = "PARSE_FAILED"
    message = str(exc).strip() or type(exc).__name__
    return JobError(code=code, message=message, stage_id=stage_id)
