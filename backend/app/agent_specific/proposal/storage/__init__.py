"""Proposal artifact persistence (local disk and Vercel Blob)."""

from __future__ import annotations

import importlib

_persistence = importlib.import_module(".persistence", __name__)
for _name in dir(_persistence):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_persistence, _name)
del _persistence, _name, importlib
