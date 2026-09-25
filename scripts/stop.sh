#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Stopping frontend..."
"$ROOT/frontend/scripts/stop.sh" || true

echo ""
echo "==> Stopping backend..."
"$ROOT/backend/scripts/stop.sh" || true

echo ""
echo "==> Stopping parse-pipeline..."
"$ROOT/parse-pipeline/scripts/stop.sh" || true

echo ""
echo "Platform stopped."
