#!/usr/bin/env python3
"""Build an E2B custom template with Slidev dependencies preinstalled.

Run once (or when Slidev deps change):

    cd backend
    uv run python scripts/e2b_build_slidev_template.py --alias slidev-builder-v1

Then set in .env:

    E2B_SLIDEV_TEMPLATE=slidev-builder-v1

Requires: uv pip install e2b
Docs: https://e2b.dev/docs/sandbox-template
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
_TEMPLATE_PACKAGE_REL = "app/sandbox/templates/template-package.json"
_TEMPLATE_PACKAGE = _BACKEND_ROOT / _TEMPLATE_PACKAGE_REL
_WORKDIR = "/opt/slidev"


def _load_env() -> None:
    env_file = _BACKEND_ROOT / ".env"
    env_local = _BACKEND_ROOT / ".env.local"
    legacy_env = _BACKEND_ROOT.parent / ".env"
    if env_file.is_file():
        load_dotenv(env_file)
    elif legacy_env.is_file():
        load_dotenv(legacy_env)
    if env_local.is_file():
        load_dotenv(env_local, override=True)


def _resolve_api_key(explicit: str | None) -> str:
    api_key = (explicit or os.environ.get("E2B_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit(
            "E2B_API_KEY is not set.\n"
            "Add it to backend/.env (or backend/.env.local), or pass --api-key.\n"
            "Get a key: https://e2b.dev/dashboard?tab=keys"
        )
    return api_key


def main() -> None:
    _load_env()

    parser = argparse.ArgumentParser(description="Build E2B Slidev sandbox template")
    parser.add_argument(
        "--alias",
        default="slidev-builder-v1",
        help="E2B template alias (default: slidev-builder-v1)",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="E2B API key (defaults to E2B_API_KEY from backend/.env)",
    )
    parser.add_argument(
        "--with-pdf",
        action="store_true",
        help="Also install playwright-chromium for PDF export in the template",
    )
    args = parser.parse_args()

    try:
        from e2b import Template, default_build_logger
    except ImportError as exc:
        raise SystemExit(
            "Missing e2b SDK. Install with: uv pip install e2b\n"
            "See https://e2b.dev/docs/sandbox-template"
        ) from exc

    if not _TEMPLATE_PACKAGE.is_file():
        raise SystemExit(f"Template package.json not found: {_TEMPLATE_PACKAGE}")

    api_key = _resolve_api_key(args.api_key)

    # E2B .copy() only accepts paths relative to file_context_path (not absolute).
    template = (
        Template(file_context_path=_BACKEND_ROOT)
        .from_node_image("24")
        .set_workdir(_WORKDIR)
        .copy(_TEMPLATE_PACKAGE_REL, "package.json")
        .run_cmd("npm install --no-audit --no-fund")
    )
    if args.with_pdf:
        template = template.run_cmd("npm install --no-audit --no-fund playwright-chromium").run_cmd(
            "npx playwright install chromium"
        )

    print(f"Building E2B template alias={args.alias!r} (with_pdf={args.with_pdf}) ...")
    Template.build(
        template,
        alias=args.alias,
        on_build_logs=default_build_logger(),
        api_key=api_key,
    )
    print(f"Done. Set E2B_SLIDEV_TEMPLATE={args.alias}")


if __name__ == "__main__":
    main()
