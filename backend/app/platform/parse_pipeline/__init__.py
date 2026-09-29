"""Platform client for parse-pipeline worker (HTTP service or GHA dispatch)."""

from app.platform.parse_pipeline.enqueue import enqueue_parse_job

__all__ = ["enqueue_parse_job"]
