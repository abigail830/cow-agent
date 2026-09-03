#!/usr/bin/env python3
"""Upload non-sensitive env vars from a .env file to a linked Vercel project."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend" if (ROOT / "backend" / ".env.example").exists() else ROOT
DEFAULT_SENSITIVE_FILE = (
    Path(__file__).resolve().parent / "vercel-env.sensitive-keys.txt"
    if (Path(__file__).resolve().parent / "vercel-env.sensitive-keys.txt").exists()
    else ROOT / "scripts" / "vercel-env.sensitive-keys.txt"
)
DEFAULT_ENVIRONMENTS = ("production", "preview", "development")
PLACEHOLDER_RE = re.compile(r"<[^>]+>")


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(";"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if not key:
            continue
        value = strip_env_value(value)
        values[key] = value
    return values


def strip_env_value(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    if value[0] in "\"'" and value[-1] == value[0]:
        return value[1:-1]
    for sep in (" #", "\t#", " ;", "\t;"):
        if sep in value:
            value = value.split(sep, 1)[0].strip()
    return value.strip("\"'")


def load_sensitive_keys(path: Path | None, extra: list[str]) -> set[str]:
    keys: set[str] = set(extra)
    if path is None or not path.exists():
        return keys
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        keys.add(line.split("#", 1)[0].strip())
    return keys


def is_placeholder(value: str) -> bool:
    if not value:
        return True
    if PLACEHOLDER_RE.search(value):
        return True
    if value in {"user:pass@host", "user:pass@host/db"}:
        return True
    return False


def vercel_whoami(cwd: Path) -> str | None:
    result = subprocess.run(
        ["vercel", "whoami"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if not lines:
        return None
    username = lines[-1]
    if username.startswith("Vercel CLI"):
        return None
    return username


def load_expected_vercel_user(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        return line.split("#", 1)[0].strip()
    return None


def check_vercel_account(
    cwd: Path,
    *,
    expected: str | None,
    dry_run: bool,
    skip_check: bool,
) -> int:
    current = vercel_whoami(cwd)
    if current:
        print(f"Vercel account: {current}")
    elif not dry_run:
        print("Warning: could not read Vercel account (`vercel whoami`). Run `vercel login`.", file=sys.stderr)

    if skip_check or not expected or dry_run:
        return 0

    if current != expected:
        print(
            f"Error: Vercel CLI is logged in as '{current or 'unknown'}', expected '{expected}'.\n"
            "Git user.email does NOT control Vercel login. Switch account with:\n"
            "  vercel logout\n"
            "  export VERCEL_TOKEN='vercel_...'   # from abigail830 dashboard → Tokens\n"
            "  vercel whoami\n"
            "Or pass --skip-vercel-user-check to override.",
            file=sys.stderr,
        )
        return 1
    return 0


def vercel_env_exists(key: str, environment: str, cwd: Path) -> bool:
    result = subprocess.run(
        ["vercel", "env", "ls", environment, "--json"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    return f"\"key\":\"{key}\"" in result.stdout or f'"key": "{key}"' in result.stdout


def add_vercel_env(
    key: str,
    value: str,
    environment: str,
    *,
    cwd: Path,
    force: bool,
    sensitive: bool,
    dry_run: bool,
) -> None:
    flag = " (sensitive)" if sensitive else ""
    print(f"  [{environment}] {key}{flag} = {value[:48]}{'…' if len(value) > 48 else ''}")
    if dry_run:
        return

    cmd = ["vercel", "env", "add", key, environment]
    if force:
        cmd.append("--force")
    if sensitive:
        cmd.append("--sensitive")

    result = subprocess.run(
        cmd,
        cwd=cwd,
        input=value,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"failed to set {key} for {environment}: {stderr}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Upload non-sensitive variables from a .env file to Vercel.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview what would be uploaded (backend repo linked via `vercel link`)
  python scripts/sync_vercel_env.py --cwd backend --from backend/.env.example --dry-run

  # Upload safe defaults from .env.example
  python scripts/sync_vercel_env.py --cwd backend --from backend/.env.example

  # Upload non-sensitive values from your local .env
  python scripts/sync_vercel_env.py --cwd backend --from backend/.env

  # Also upload secrets from local .env (marks them sensitive in Vercel)
  python scripts/sync_vercel_env.py --cwd backend --from backend/.env --include-sensitive --mark-sensitive

Vercel account (NOT git user.email). If browser login loops to the wrong account:
  vercel logout
  # In a private/incognito window: log into abigail830 at vercel.com → Settings → Tokens → Create
  export VERCEL_TOKEN='vercel_...'
  vercel whoami
  python scripts/sync_vercel_env.py --expected-vercel-user YOUR_VERCEL_USERNAME
        """,
    )
    parser.add_argument(
        "--cwd",
        type=Path,
        default=BACKEND_ROOT,
        help="Vercel project directory (must contain or link .vercel/project.json)",
    )
    parser.add_argument(
        "--from",
        dest="env_file",
        type=Path,
        default=BACKEND_ROOT / ".env.example",
        help="Source .env or .env.example file",
    )
    parser.add_argument(
        "--environment",
        action="append",
        dest="environments",
        choices=DEFAULT_ENVIRONMENTS,
        help="Target Vercel environment (repeatable; default: all three)",
    )
    parser.add_argument(
        "--sensitive-keys-file",
        type=Path,
        default=DEFAULT_SENSITIVE_FILE,
        help="File listing keys to skip unless --include-sensitive is set",
    )
    parser.add_argument(
        "--skip",
        action="append",
        default=[],
        metavar="KEY",
        help="Additional keys to skip",
    )
    parser.add_argument(
        "--include-sensitive",
        action="store_true",
        help="Also upload keys listed in the sensitive-keys file",
    )
    parser.add_argument(
        "--mark-sensitive",
        action="store_true",
        help="When uploading sensitive keys, pass --sensitive to Vercel CLI",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing Vercel env vars (--force)",
    )
    parser.add_argument(
        "--include-empty",
        action="store_true",
        help="Upload keys with empty values too",
    )
    parser.add_argument(
        "--include-placeholders",
        action="store_true",
        help="Upload placeholder values like https://<resource>....",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print actions without calling Vercel CLI",
    )
    parser.add_argument(
        "--expected-vercel-user",
        type=str,
        default=None,
        help="Abort unless `vercel whoami` matches this Vercel username",
    )
    parser.add_argument(
        "--expected-vercel-user-file",
        type=Path,
        default=Path(__file__).resolve().parent / "vercel-env.expected-user",
        help="Optional file with expected Vercel username (one line)",
    )
    parser.add_argument(
        "--skip-vercel-user-check",
        action="store_true",
        help="Skip Vercel account verification",
    )
    args = parser.parse_args()

    if shutil.which("vercel") is None:
        print("Error: Vercel CLI not found. Install: npm i -g vercel", file=sys.stderr)
        return 1

    cwd = args.cwd.resolve()
    env_file = args.env_file.resolve()
    if not env_file.exists():
        print(f"Error: env file not found: {env_file}", file=sys.stderr)
        return 1

    vercel_dir = cwd / ".vercel"
    if not args.dry_run and not vercel_dir.exists():
        print(
            f"Error: {cwd} is not linked to Vercel. Run:\n  cd {cwd} && vercel link",
            file=sys.stderr,
        )
        return 1

    expected_user = args.expected_vercel_user or load_expected_vercel_user(args.expected_vercel_user_file)
    if check_vercel_account(
        cwd,
        expected=expected_user,
        dry_run=args.dry_run,
        skip_check=args.skip_vercel_user_check,
    ):
        return 1

    environments = tuple(args.environments or DEFAULT_ENVIRONMENTS)
    sensitive_keys = load_sensitive_keys(args.sensitive_keys_file, args.skip)
    values = parse_env_file(env_file)

    to_upload: list[tuple[str, str, bool]] = []
    skipped_sensitive: list[str] = []
    skipped_empty: list[str] = []
    skipped_placeholder: list[str] = []

    for key in sorted(values):
        value = values[key]
        is_sensitive = key in sensitive_keys

        if is_sensitive and not args.include_sensitive:
            skipped_sensitive.append(key)
            continue
        if not value and not args.include_empty:
            skipped_empty.append(key)
            continue
        if is_placeholder(value) and not args.include_placeholders:
            skipped_placeholder.append(key)
            continue

        to_upload.append((key, value, is_sensitive and args.mark_sensitive))

    print(f"Project cwd: {cwd}")
    print(f"Source file: {env_file}")
    print(f"Environments: {', '.join(environments)}")
    print(f"Will upload: {len(to_upload)} variable(s)")
    if skipped_sensitive:
        print(f"Skipped sensitive ({len(skipped_sensitive)}): {', '.join(skipped_sensitive)}")
    if skipped_empty:
        print(f"Skipped empty ({len(skipped_empty)}): {', '.join(skipped_empty)}")
    if skipped_placeholder:
        print(f"Skipped placeholders ({len(skipped_placeholder)}): {', '.join(skipped_placeholder)}")
    print()

    if not to_upload:
        print("Nothing to upload.")
        return 0

    uploaded = 0
    for key, value, mark_sensitive in to_upload:
        print(f"{key}:")
        for environment in environments:
            if not args.force and not args.dry_run and vercel_env_exists(key, environment, cwd):
                print(f"  [{environment}] skip (already exists; use --force to overwrite)")
                continue
            try:
                add_vercel_env(
                    key,
                    value,
                    environment,
                    cwd=cwd,
                    force=args.force,
                    sensitive=mark_sensitive,
                    dry_run=args.dry_run,
                )
                uploaded += 1
            except RuntimeError as exc:
                print(f"Error: {exc}", file=sys.stderr)
                return 1
        print()

    action = "Would upload" if args.dry_run else "Uploaded"
    print(f"{action} {uploaded} env assignment(s).")
    if skipped_sensitive and not args.include_sensitive:
        print("\nSet sensitive vars manually in Vercel Dashboard → Settings → Environment Variables.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
