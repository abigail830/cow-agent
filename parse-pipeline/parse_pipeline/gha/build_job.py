"""Build job JSON for GitHub Actions workflow_dispatch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


def _file_uri(path: Path) -> str:
    return path.resolve().as_uri()


def build_job_payload(
    *,
    pipeline_id: str,
    out_dir: Path,
    source_path: Path | None = None,
    source_url: str | None = None,
    filename: str | None = None,
    job_id: str | None = None,
    webhook_url: str | None = None,
    webhook_secret: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    if source_path is None and source_url is None:
        raise ValueError("provide source_path or source_url")
    if source_path is not None and source_url is not None:
        raise ValueError("provide only one of source_path or source_url")

    if source_path is not None:
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        read_url = _file_uri(source_path)
        fname = filename or source_path.name
        size_bytes = source_path.stat().st_size
    else:
        assert source_url is not None
        parsed = urlparse(source_url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("source_url must be http(s)")
        read_url = source_url
        fname = filename or Path(parsed.path).name or "document"
        size_bytes = None

    out_dir.mkdir(parents=True, exist_ok=True)
    callbacks: dict = {}
    if webhook_url and webhook_secret:
        callbacks = {
            "webhook_url": webhook_url,
            "webhook_secret": webhook_secret,
            "events": ["stage.updated", "job.completed", "job.failed"],
        }

    read_spec: dict = {"url": read_url, "method": "GET", "filename": fname}
    if size_bytes is not None:
        read_spec["size_bytes"] = size_bytes

    payload = {
        "schema_version": "1.0",
        "job_id": job_id,
        "idempotency_key": idempotency_key,
        "pipeline_id": pipeline_id,
        "storage": {
            "read": read_spec,
            "write": {
                "content_md": {
                    "url": _file_uri(out_dir / "content.md"),
                    "method": "PUT",
                    "content_type": "text/markdown; charset=utf-8",
                },
                "meta_json": {
                    "url": _file_uri(out_dir / "meta.json"),
                    "method": "PUT",
                    "content_type": "application/json",
                },
                "pageindex_json": {
                    "url": _file_uri(out_dir / "pageindex.json"),
                    "method": "PUT",
                    "content_type": "application/json",
                },
            },
        },
        "source": {"filename": fname, "source_type": "gha"},
        "options": {},
        "callbacks": callbacks,
    }
    return {k: v for k, v in payload.items() if v is not None}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build job JSON for parse-pipeline GHA runner")
    parser.add_argument("--pipeline-id", required=True)
    parser.add_argument("--source-path", type=Path, default=None)
    parser.add_argument("--source-url", default=None)
    parser.add_argument("--filename", default=None)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--job-id", default=None)
    parser.add_argument("--idempotency-key", default=None)
    parser.add_argument("--webhook-url", default=None)
    parser.add_argument("--webhook-secret", default=None)
    parser.add_argument("--output", type=Path, required=True, help="Write job JSON here")
    args = parser.parse_args()

    payload = build_job_payload(
        pipeline_id=args.pipeline_id,
        out_dir=args.out_dir,
        source_path=args.source_path,
        source_url=args.source_url,
        filename=args.filename,
        job_id=args.job_id,
        idempotency_key=args.idempotency_key,
        webhook_url=args.webhook_url,
        webhook_secret=args.webhook_secret,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
