from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from parse_pipeline.normalize.artifacts import NormalizedArtifacts
from parse_pipeline.schemas.storage import StorageSpec, WriteTarget
from parse_pipeline.storage.io import write_normalized_artifacts


@pytest.mark.asyncio
async def test_write_normalized_artifacts_uploads_in_parallel() -> None:
    spec = StorageSpec(
        write={
            "content_md": WriteTarget(url="https://example.test/artifacts/content_md", method="PUT"),
            "meta_json": WriteTarget(url="https://example.test/artifacts/meta_json", method="PUT"),
        }
    )
    normalized = NormalizedArtifacts(
        content_md="# Title",
        meta_json={"line_count": 1},
        pageindex_json=None,
        figure_files={
            "f1": (b"img1", "image/png", "png"),
            "f2": (b"img2", "image/jpeg", "jpeg"),
        },
    )
    call_order: list[str] = []

    async def fake_write_artifact(_spec, key, _data, *, client=None):
        call_order.append(f"artifact:{key}")
        await asyncio.sleep(0.05)
        return True

    async def fake_write_figure(_spec, figure_id, _data, _mime, _ext, *, client=None):
        call_order.append(f"figure:{figure_id}")
        await asyncio.sleep(0.05)
        return True

    with (
        patch("parse_pipeline.storage.io.write_artifact", side_effect=fake_write_artifact),
        patch("parse_pipeline.storage.io.write_figure", side_effect=fake_write_figure),
    ):
        result = await write_normalized_artifacts(spec, normalized)

    assert result.wrote_content is True
    assert result.wrote_meta is True
    assert result.figure_writes == 2
    assert len(call_order) == 4
    assert call_order.count("artifact:content_md") == 1
    assert call_order.count("artifact:meta_json") == 1
    assert call_order.count("figure:f1") == 1
    assert call_order.count("figure:f2") == 1
