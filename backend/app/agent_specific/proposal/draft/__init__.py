"""Proposal draft state, fee tables, placeholders, and preview."""

from __future__ import annotations

import importlib

_draft = importlib.import_module(".draft", __name__)
for _name in dir(_draft):
    if _name.startswith("__"):
        continue
    globals()[_name] = getattr(_draft, _name)
del _draft, _name, importlib
