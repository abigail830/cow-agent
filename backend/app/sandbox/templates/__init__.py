from __future__ import annotations

from pathlib import Path

_TEMPLATES_DIR = Path(__file__).resolve().parent
SLIDEV_PACKAGE_JSON = (_TEMPLATES_DIR / "package.json").read_text(encoding="utf-8")
