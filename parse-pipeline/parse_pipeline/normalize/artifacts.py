from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from parse_pipeline.normalize.line_index import build_line_index


@dataclass
class NormalizedArtifacts:
    content_md: str
    meta_json: dict[str, Any]
    pageindex_json: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)


def normalize_text_artifacts(
    *,
    content: str,
    job_id: str,
    pipeline_id: str,
    parse_engine: str,
    provider_id: str | None = None,
    pageindex: dict[str, Any] | None = None,
    warnings: list[str] | None = None,
    duration_ms: int | None = None,
) -> NormalizedArtifacts:
    line_count, pages, sections = build_line_index(content)
    meta: dict[str, Any] = {
        "schema_version": "1.0",
        "parse_status": "ready",
        "parse_engine": parse_engine,
        "provider_id": provider_id or parse_engine,
        "pipeline_id": pipeline_id,
        "job_id": job_id,
        "content_path": "content.md",
        "line_count": line_count,
        "page_count": len(pages),
        "pages": pages,
        "sections": sections,
        "warnings": warnings or [],
    }
    if pageindex is not None:
        meta["pageindex_path"] = "pageindex.json"
    if duration_ms is not None:
        meta["stats"] = {"duration_ms": duration_ms}
    return NormalizedArtifacts(
        content_md=content,
        meta_json=meta,
        pageindex_json=pageindex,
        warnings=warnings or [],
    )


def artifacts_to_bytes(artifacts: NormalizedArtifacts) -> tuple[bytes, bytes, bytes | None]:
    content_bytes = artifacts.content_md.encode("utf-8")
    meta_bytes = json.dumps(artifacts.meta_json, ensure_ascii=False, indent=2).encode("utf-8")
    pageindex_bytes = None
    if artifacts.pageindex_json is not None:
        pageindex_bytes = json.dumps(artifacts.pageindex_json, ensure_ascii=False, indent=2).encode("utf-8")
    return content_bytes, meta_bytes, pageindex_bytes
