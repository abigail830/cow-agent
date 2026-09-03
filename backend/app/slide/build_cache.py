"""Content-addressed cache for Slidev build outputs."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from app.config import get_settings
from app.proposal.blob_client import blob_get, blob_put, blob_storage_enabled
from app.sandbox.types import SlidevBuildOutput

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_CACHE_ROOT = _BACKEND_ROOT / "data" / "slide-build-cache"
_BLOB_PREFIX = "slide-build-cache"


def slide_build_cache_key(
    slides_md: str,
    *,
    export_pdf: bool,
    provider: str,
    template: str | None,
) -> str:
    digest = hashlib.sha256()
    digest.update(slides_md.encode("utf-8"))
    digest.update(
        f"|provider={provider}|pdf={export_pdf}|template={template or ''}".encode("utf-8"),
    )
    return digest.hexdigest()[:32]


def _manifest_blob_path(cache_key: str) -> str:
    return f"{_BLOB_PREFIX}/{cache_key}/manifest.json"


def _dist_blob_path(cache_key: str, rel_path: str) -> str:
    rel = rel_path.lstrip("/").replace("\\", "/")
    return f"{_BLOB_PREFIX}/{cache_key}/dist/{rel}"


def _local_manifest_path(cache_key: str) -> Path:
    return _CACHE_ROOT / cache_key / "manifest.json"


def _local_dist_path(cache_key: str, rel_path: str) -> Path:
    rel = rel_path.lstrip("/").replace("\\", "/")
    return _CACHE_ROOT / cache_key / "dist" / rel


def _load_manifest(cache_key: str) -> dict | None:
    if blob_storage_enabled():
        raw = blob_get(_manifest_blob_path(cache_key))
        if not raw:
            return None
        try:
            payload = json.loads(raw.decode("utf-8"))
            return payload if isinstance(payload, dict) else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None

    path = _local_manifest_path(cache_key)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_manifest(cache_key: str, manifest: dict) -> None:
    payload = json.dumps(manifest)
    if blob_storage_enabled():
        blob_put(_manifest_blob_path(cache_key), payload, content_type="application/json")
        return
    path = _local_manifest_path(cache_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _read_bytes(cache_key: str, rel_path: str) -> bytes | None:
    if blob_storage_enabled():
        return blob_get(_dist_blob_path(cache_key, rel_path))
    path = _local_dist_path(cache_key, rel_path)
    if not path.is_file():
        return None
    return path.read_bytes()


def _write_bytes(cache_key: str, rel_path: str, data: bytes, *, content_type: str) -> None:
    if blob_storage_enabled():
        blob_put(_dist_blob_path(cache_key, rel_path), data, content_type=content_type)
        return
    path = _local_dist_path(cache_key, rel_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def get_cached_build(cache_key: str) -> SlidevBuildOutput | None:
    settings = get_settings()
    if not settings.sandbox_slidev_cache:
        return None

    manifest = _load_manifest(cache_key)
    if not manifest:
        return None

    dist_index = manifest.get("dist_files")
    if not isinstance(dist_index, dict) or not dist_index:
        return None

    dist_files: dict[str, bytes] = {}
    for rel in dist_index:
        rel_str = str(rel).lstrip("/")
        if not rel_str or ".." in rel_str.split("/"):
            continue
        raw = _read_bytes(cache_key, rel_str)
        if raw is None:
            logger.debug("Slide build cache miss: missing dist file %s", rel_str)
            return None
        dist_files[rel_str] = raw

    pdf_bytes: bytes | None = None
    if manifest.get("has_pdf"):
        pdf_bytes = _read_bytes(cache_key, "deck.pdf")

    return SlidevBuildOutput(
        dist_files=dist_files,
        pdf_bytes=pdf_bytes,
        logs=f"Slide build cache hit ({cache_key}).",
    )


def put_cached_build(cache_key: str, output: SlidevBuildOutput) -> None:
    settings = get_settings()
    if not settings.sandbox_slidev_cache:
        return
    if output.error or not output.dist_files:
        return

    dist_index = sorted(output.dist_files.keys())
    manifest = {
        "cache_key": cache_key,
        "dist_files": {rel: rel for rel in dist_index},
        "has_pdf": output.pdf_bytes is not None,
    }
    try:
        for rel, data in output.dist_files.items():
            rel_str = rel.lstrip("/").replace("\\", "/")
            if not rel_str or ".." in rel_str.split("/"):
                continue
            _write_bytes(cache_key, rel_str, data, content_type="application/octet-stream")
        if output.pdf_bytes:
            _write_bytes(cache_key, "deck.pdf", output.pdf_bytes, content_type="application/pdf")
        _write_manifest(cache_key, manifest)
    except Exception:
        logger.warning("Failed to write slide build cache %s", cache_key, exc_info=True)
