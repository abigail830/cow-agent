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
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.request(read_spec.method, read_spec.url)
        response.raise_for_status()
        return response.content


async def put_bytes(target: WriteTarget, data: bytes) -> None:
    parsed = urlparse(target.url)
    if parsed.scheme == "file":
        path = _file_path_from_url(target.url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return
    headers: dict[str, str] = {}
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
