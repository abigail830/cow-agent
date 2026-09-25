from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from parse_pipeline.api.app import create_app
from parse_pipeline.job_store.factory import reset_job_store

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def client():
    reset_job_store()
    return TestClient(create_app())


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "parse-pipeline"


def test_create_and_get_text_job(client: TestClient, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    source = FIXTURES / "sample.md"

    payload = {
        "pipeline_id": "text_standard",
        "storage": {
            "read": {"url": source.as_uri(), "filename": "sample.md"},
            "write": {
                "content_md": {"url": (out_dir / "content.md").as_uri(), "method": "PUT"},
                "meta_json": {"url": (out_dir / "meta.json").as_uri(), "method": "PUT"},
            },
        },
        "source": {"filename": "sample.md"},
    }
    headers = {"Authorization": "Bearer test_dev_key", "X-Parse-Caller-Id": "test"}

    create_resp = client.post("/v1/jobs", json=payload, headers=headers)
    assert create_resp.status_code == 202
    job_id = create_resp.json()["job_id"]

    # background task runs synchronously in TestClient for async endpoints in same thread
    for _ in range(50):
        get_resp = client.get(f"/v1/jobs/{job_id}", headers=headers)
        assert get_resp.status_code == 200
        body = get_resp.json()
        if body["status"] in {"succeeded", "failed"}:
            break
        time.sleep(0.05)
    else:
        pytest.fail("job did not finish in time")

    assert body["status"] == "succeeded"
    assert (out_dir / "content.md").exists()
    assert len(body["stages"]) == 8


def test_create_job_honors_platform_job_id(client: TestClient, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    source = FIXTURES / "sample.md"
    platform_job_id = "job_platform_fixed_id"
    payload = {
        "job_id": platform_job_id,
        "pipeline_id": "text_standard",
        "storage": {
            "read": {"url": source.as_uri(), "filename": "sample.md"},
            "write": {
                "content_md": {"url": (out_dir / "content.md").as_uri(), "method": "PUT"},
                "meta_json": {"url": (out_dir / "meta.json").as_uri(), "method": "PUT"},
            },
        },
    }
    headers = {"Authorization": "Bearer test_dev_key", "X-Parse-Caller-Id": "test"}
    create_resp = client.post("/v1/jobs", json=payload, headers=headers)
    assert create_resp.status_code == 202
    assert create_resp.json()["job_id"] == platform_job_id


def test_auth_required(client: TestClient) -> None:
    response = client.post("/v1/jobs", json={"pipeline_id": "text_standard", "storage": {}})
    assert response.status_code == 401
