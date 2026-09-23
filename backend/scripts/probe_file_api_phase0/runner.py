"""Orchestrate Phase 0 probes and emit a JSON report."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.config import get_settings

from scripts.probe_file_api_phase0.dashscope_probes import run_dashscope_probes
from scripts.probe_file_api_phase0.deepseek_probes import run_deepseek_probes
from scripts.probe_file_api_phase0.http_client import OpenAICompatibleClient
from scripts.probe_file_api_phase0.report import ProbeReport, ProbeResult, ProbeStatus, new_report


DEFAULT_DASHSCOPE_MODELS = {
    "qwen_long": "qwen-long",
    "qwen37": "qwen3.7-plus",
    "qwen38": "qwen3.8-max",
}


async def run_all_probes(*, skip_deepseek: bool = False, skip_dashscope: bool = False) -> ProbeReport:
    settings = get_settings()
    report = new_report()

    if not skip_dashscope:
        if not settings.dashscope_api_key:
            report.add(
                ProbeResult(
                    id="dashscope.config",
                    label="DashScope API key",
                    status=ProbeStatus.SKIP,
                    detail="DASHSCOPE_API_KEY not set",
                )
            )
        else:
            client = OpenAICompatibleClient(
                api_key=settings.dashscope_api_key,
                base_url=settings.dashscope_base_url,
            )
            await run_dashscope_probes(client, report, models=DEFAULT_DASHSCOPE_MODELS)

    if not skip_deepseek:
        if not settings.deepseek_api_key:
            report.add(
                ProbeResult(
                    id="deepseek.config",
                    label="DeepSeek API key",
                    status=ProbeStatus.SKIP,
                    detail="DEEPSEEK_API_KEY not set",
                )
            )
        else:
            client = OpenAICompatibleClient(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            )
            await run_deepseek_probes(client, report, chat_model="deepseek-flash")

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 0 file API live probes (domestic models)")
    parser.add_argument("--skip-dashscope", action="store_true")
    parser.add_argument("--skip-deepseek", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write JSON report to this path (default: stdout only)",
    )
    args = parser.parse_args(argv)

    report = asyncio.run(
        run_all_probes(skip_deepseek=args.skip_deepseek, skip_dashscope=args.skip_dashscope)
    )
    text = report.to_json()
    print(text)
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"\nWrote report to {args.output}")

    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
