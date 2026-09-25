from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from parse_pipeline.normalize.artifacts import NormalizedArtifacts, artifacts_to_bytes
from parse_pipeline.schemas.storage import ReadSpec, StorageSpec, WriteTarget

_HTTP_TIMEOUT = 120.0


def _file_path_from_url(url: str) -> Path:
    parsed = urlparse(url)
    if parsed.scheme != "file":
        raise ValueError(f"unsupported file URL scheme: {parsed.scheme}")
    return Path(unquote(parsed.path))


@asynccontextmanager
async def http_put_client() -> AsyncIterator[httpx.AsyncClient]:
    client = httpx.AsyncClient(timeout=_HTTP_TIMEOUT)
    try:
        yield client
    finally:
        await client.aclose()


async def fetch_bytes(read_spec: ReadSpec) -> bytes:
    parsed = urlparse(read_spec.url)
    if parsed.scheme == "file":
        path = _file_path_from_url(read_spec.url)
        return path.read_bytes()
    headers = dict(read_spec.headers or {})
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        response = await client.request(read_spec.method, read_spec.url, headers=headers)
        response.raise_for_status()
        return response.content


async def put_bytes(
    target: WriteTarget,
    data: bytes,
    *,
    client: httpx.AsyncClient | None = None,
) -> None:
    parsed = urlparse(target.url)
    if parsed.scheme == "file":
        path = _file_path_from_url(target.url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return
    headers: dict[str, str] = dict(target.headers or {})
    if target.content_type:
        headers["Content-Type"] = target.content_type
    if client is not None:
        response = await client.request(target.method, target.url, content=data, headers=headers)
        response.raise_for_status()
        return
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as ephemeral:
        response = await ephemeral.request(target.method, target.url, content=data, headers=headers)
        response.raise_for_status()


def parse_storage_spec(raw: dict) -> StorageSpec:
    return StorageSpec.model_validate(raw)


async def write_artifact(
    spec: StorageSpec,
    key: str,
    data: bytes,
    *,
    client: httpx.AsyncClient | None = None,
) -> bool:
    target = spec.write.get(key)
    if target is None:
        return False
    await put_bytes(target, data, client=client)
    return True


def _figure_write_url(content_target: WriteTarget, figure_id: str, ext: str) -> str:
    url = content_target.url
    parsed = urlparse(url)
    if parsed.scheme == "file":
        content_path = _file_path_from_url(url)
        figure_path = content_path.parent / "figures" / f"{figure_id}.{ext}"
        return figure_path.as_uri()
    if "/artifacts/" in url:
        # Platform API: PUT /figures/{figure_id} — extension comes from Content-Type, not path.
        base = url.rsplit("/artifacts/", 1)[0]
        return f"{base}/figures/{figure_id}"
    raise ValueError(f"cannot derive figure write URL from: {url}")


async def write_figure(
    spec: StorageSpec,
    figure_id: str,
    data: bytes,
    mime_type: str,
    ext: str,
    *,
    client: httpx.AsyncClient | None = None,
) -> bool:
    content_target = spec.write.get("content_md")
    if content_target is None:
        return False
    target = WriteTarget(
        url=_figure_write_url(content_target, figure_id, ext),
        method=content_target.method,
        content_type=mime_type,
        headers=content_target.headers,
    )
    await put_bytes(target, data, client=client)
    return True


@dataclass(frozen=True)
class WriteBatchResult:
    wrote_content: bool
    wrote_meta: bool
    wrote_pageindex: bool
    figure_writes: int


async def write_normalized_artifacts(spec: StorageSpec, normalized: NormalizedArtifacts) -> WriteBatchResult:
    content_b, meta_b, pageindex_b = artifacts_to_bytes(normalized)
    async with http_put_client() as client:
        artifact_tasks: list[asyncio.Task[bool]] = [
            asyncio.create_task(write_artifact(spec, "content_md", content_b, client=client)),
            asyncio.create_task(write_artifact(spec, "meta_json", meta_b, client=client)),
        ]
        if pageindex_b is not None:
            artifact_tasks.append(
                asyncio.create_task(write_artifact(spec, "pageindex_json", pageindex_b, client=client)),
            )
        artifact_results = await asyncio.gather(*artifact_tasks)
        wrote_content = artifact_results[0]
        wrote_meta = artifact_results[1]
        wrote_pageindex = artifact_results[2] if pageindex_b is not None else False

        figure_tasks = [
            asyncio.create_task(write_figure(spec, figure_id, data, mime_type, ext, client=client))
            for figure_id, (data, mime_type, ext) in normalized.figure_files.items()
        ]
        figure_results = await asyncio.gather(*figure_tasks) if figure_tasks else []
    return WriteBatchResult(
        wrote_content=wrote_content,
        wrote_meta=wrote_meta,
        wrote_pageindex=wrote_pageindex,
        figure_writes=sum(1 for wrote in figure_results if wrote),
    )
