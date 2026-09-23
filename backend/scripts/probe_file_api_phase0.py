"""CLI entry: python scripts/probe_file_api_phase0.py [--output report.json]"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.probe_file_api_phase0.runner import main

if __name__ == "__main__":
    raise SystemExit(main())
