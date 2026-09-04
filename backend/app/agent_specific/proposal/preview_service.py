"""Backward-compatible re-exports for proposal preview API helpers."""

from __future__ import annotations

import importlib

_preview = importlib.import_module(".draft.preview_service", "app.agent_specific.proposal")
for _name in dir(_preview):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_preview, _name)
del _preview, _name, importlib
