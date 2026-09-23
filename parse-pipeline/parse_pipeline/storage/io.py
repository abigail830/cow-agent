from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from parse_pipeline.schemas.storage import ReadSpec, StorageSpec, WriteTarget


def _file_path_from_url(url: str) -> Path:
    parsed = urlparse(url)
    if parsed.scheme != "file":
        raise ValueError(f"unsupported file URL scheme: {parsed.scheme}")
    return Path(unquote(parsed.path))


async def fetch_bytes(read_spec: ReadSpec) -> bytes:
    parsed = urlparse(read_spec.url)
    if parsed.scheme == "file":
        path = _file_path_from_url(read_spec.url)
        return path.read_bytes()
    headers = dict(read_spec.headers or {})
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.request(read_spec.method, read_spec.url, headers=headers)
        response.raise_for_status()
        return response.content


async def put_bytes(target: WriteTarget, data: bytes) -> None:
    parsed = urlparse(target.url)
    if parsed.scheme == "file":
        path = _file_path_from_url(target.url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return
    headers: dict[str, str] = dict(target.headers or {})
    if target.content_type:
        headers["Content-Type"] = target.content_type
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.request(target.method, target.url, content=data, headers=headers)
        response.raise_for_status()


def parse_storage_spec(raw: dict) -> StorageSpec:
    return StorageSpec.model_validate(raw)


async def write_artifact(spec: StorageSpec, key: str, data: bytes) -> bool:
    target = spec.write.get(key)
    if target is None:
        return False
    await put_bytes(target, data)
    return True


def _figure_write_url(content_target: WriteTarget, figure_id: str, ext: str) -> str:
    url = content_target.url
    parsed = urlparse(url)
    if parsed.scheme == "file":
        content_path = _file_path_from_url(url)
        figure_path = content_path.parent / "figures" / f"{figure_id}.{ext}"
        return figure_path.as_uri()
    if "/artifacts/" in url:
        base = url.rsplit("/artifacts/", 1)[0]
        return f"{base}/figures/{figure_id}.{ext}"
    raise ValueError(f"cannot derive figure write URL from: {url}")


async def write_figure(
    spec: StorageSpec,
    figure_id: str,
    data: bytes,
    mime_type: str,
    ext: str,
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
    await put_bytes(target, data)
    return True
