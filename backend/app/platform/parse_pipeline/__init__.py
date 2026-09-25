"""Platform client for parse-pipeline worker (HTTP service / GHA / legacy inline)."""

from app.platform.parse_pipeline.enqueue import enqueue_parse_job

__all__ = ["enqueue_parse_job"]
