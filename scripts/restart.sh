#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND="$ROOT/backend"
VENV="$BACKEND/.venv"

echo "==> Stopping platform..."
"$ROOT/scripts/stop.sh"

if [[ ! -x "$VENV/bin/alembic" ]] || [[ ! -x "$VENV/bin/python" ]]; then
  echo "Virtualenv not found. Run from backend/:"
  echo "  python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'"
  exit 1
fi

echo ""
echo "==> Running database migrations..."
(
  cd "$BACKEND"
  "$VENV/bin/alembic" upgrade head
)

echo ""
echo "==> Syncing agent profiles..."
(
  cd "$BACKEND"
  "$VENV/bin/python" scripts/sync_agent_profiles.py
)

echo ""
echo "==> Starting platform..."
"$ROOT/scripts/start.sh"
