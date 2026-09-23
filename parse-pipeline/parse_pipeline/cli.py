from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

import uvicorn

from parse_pipeline.config import get_settings
from parse_pipeline.job_store.base import JobRecord
from parse_pipeline.job_store.factory import get_job_store
from parse_pipeline.orchestrator.runner import JobRunner


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def cmd_serve(args: argparse.Namespace) -> None:
    settings = get_settings()
    _configure_logging(settings.log_level)
    uvicorn.run(
        "parse_pipeline.api.app:app",
        host=settings.host,
        port=settings.port,
        reload=args.reload,
    )


async def _run_job_async(job_id: str) -> int:
    runner = JobRunner()
    record = await runner.run_job(job_id)
    if record is None:
        print(f"job not found: {job_id}", file=sys.stderr)
        return 1
    print(json.dumps({"job_id": record.job_id, "status": record.status.value}, indent=2))
    return 0 if record.status.value == "succeeded" else 1


async def _run_job_from_args(args: argparse.Namespace) -> int:
    job_id = args.job_id
    if args.job_file:
        payload = json.loads(Path(args.job_file).read_text(encoding="utf-8"))
        store = get_job_store()
        job_id = job_id or payload.get("job_id") or f"job_cli_{payload.get('pipeline_id', 'run')}"
        record = JobRecord(
            job_id=job_id,
            caller_id=args.caller_id,
            pipeline_id=str(payload["pipeline_id"]),
            storage_spec=payload["storage"],
            source=payload.get("source") or {},
            options=payload.get("options") or {},
            callbacks=payload.get("callbacks") or {},
            idempotency_key=payload.get("idempotency_key"),
        )
        await store.create_job(record)
    if not job_id:
        print("provide --job-id or --job-file", file=sys.stderr)
        return 2
    return await _run_job_async(job_id)


def cmd_run_job(args: argparse.Namespace) -> None:
    _configure_logging(get_settings().log_level)
    raise SystemExit(asyncio.run(_run_job_from_args(args)))


def main() -> None:
    parser = argparse.ArgumentParser(prog="parse-pipeline")
    sub = parser.add_subparsers(dest="command")

    serve = sub.add_parser("serve", help="run HTTP API")
    serve.add_argument("--reload", action="store_true")
    serve.set_defaults(func=cmd_serve)

    run_job = sub.add_parser("run-job", help="execute a job locally (CLI / GHA entrypoint)")
    run_job.add_argument("--job-id", default=None)
    run_job.add_argument("--job-file", default=None, help="JSON job payload file")
    run_job.add_argument("--caller-id", default="cli")
    run_job.set_defaults(func=cmd_run_job)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        raise SystemExit(2)
    args.func(args)


if __name__ == "__main__":
    main()
