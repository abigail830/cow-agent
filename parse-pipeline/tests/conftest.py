from __future__ import annotations

import pytest

from parse_pipeline.config import get_settings
from parse_pipeline.job_store.factory import reset_job_store


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("JOB_STORE", "memory")
    monkeypatch.setenv("PARSE_PIPELINE_API_KEYS", "test:test_dev_key")
    get_settings.cache_clear()
    reset_job_store()
    yield
    get_settings.cache_clear()
    reset_job_store()
