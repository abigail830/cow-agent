"""Platform client for parse-pipeline worker (GHA / inline dispatch + webhooks)."""

from app.platform.parse_pipeline.enqueue import enqueue_parse_job

__all__ = ["enqueue_parse_job"]
