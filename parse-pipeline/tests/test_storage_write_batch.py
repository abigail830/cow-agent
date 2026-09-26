from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from parse_pipeline.normalize.artifacts import NormalizedArtifacts
from parse_pipeline.schemas.storage import ReadSpec, StorageSpec, WriteTarget
from parse_pipeline.storage.io import write_normalized_artifacts


@pytest.mark.asyncio
async def test_write_normalized_artifacts_uses_http_batch_when_configured() -> None:
    spec = StorageSpec(
        read=ReadSpec(url="file:///tmp/in.pdf", method="GET"),
        write={
            "artifacts_batch": WriteTarget(
                url="https://example.test/internal/parse/v1/files/abc/artifacts/batch",
                method="PUT",
                headers={"Authorization": "Bearer tok"},
            ),
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

    async def fake_batch(*_args, **_kwargs):
        call_order.append("artifact:batch")
        await asyncio.sleep(0.05)
        return True, True, False

    async def fake_write_figure(_spec, figure_id, _data, _mime, _ext, *, client=None):
        call_order.append(f"figure:{figure_id}")
        await asyncio.sleep(0.05)
        return True

    with (
        patch("parse_pipeline.storage.io.write_artifacts_batch_http", side_effect=fake_batch),
        patch("parse_pipeline.storage.io.write_artifact", new_callable=AsyncMock) as mock_single,
        patch("parse_pipeline.storage.io.write_figure", side_effect=fake_write_figure),
    ):
        result = await write_normalized_artifacts(spec, normalized)

    mock_single.assert_not_called()
    assert result.wrote_content is True
    assert result.wrote_meta is True
    assert result.figure_writes == 2
    assert call_order[0] == "artifact:batch"
    assert call_order.count("figure:f1") == 1
    assert call_order.count("figure:f2") == 1


@pytest.mark.asyncio
async def test_write_normalized_artifacts_parallel_file_scheme_without_batch() -> None:
    spec = StorageSpec(
        read=ReadSpec(url="file:///tmp/in.pdf", method="GET"),
        write={
            "content_md": WriteTarget(url="file:///tmp/out/content.md", method="PUT"),
            "meta_json": WriteTarget(url="file:///tmp/out/meta.json", method="PUT"),
        }
    )
    normalized = NormalizedArtifacts(
        content_md="# Title",
        meta_json={"line_count": 1},
        pageindex_json=None,
        figure_files={},
    )

    async def fake_write_artifact(_spec, key, _data, *, client=None):
        return True

    with patch("parse_pipeline.storage.io.write_artifact", side_effect=fake_write_artifact) as mock_single:
        result = await write_normalized_artifacts(spec, normalized)

    assert mock_single.await_count == 2
    assert result.wrote_content is True
    assert result.wrote_meta is True
