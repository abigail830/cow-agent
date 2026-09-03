"""Load templates and knowledge files for proposal-composer."""

from __future__ import annotations

from pathlib import Path
from functools import lru_cache
from typing import Any

import yaml

from app.proposal.paths import KNOWLEDGE_ROOT, TEMPLATES_ROOT


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def template_dir(template_id: str) -> Path:
    return TEMPLATES_ROOT / template_id


@lru_cache(maxsize=8)
def load_template_yaml(template_id: str) -> dict[str, Any]:
    path = template_dir(template_id) / "template.yaml"
    return _load_yaml(path)


@lru_cache(maxsize=1)
def load_templates() -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    if not TEMPLATES_ROOT.exists():
        return templates
    for path in sorted(TEMPLATES_ROOT.glob("*/template.yaml")):
        tpl = _load_yaml(path)
        template_id = str(tpl.get("template_id") or path.parent.name)
        templates.append(
            {
                "template_id": template_id,
                "display_name": tpl.get("display_name") or template_id,
                "catalog_filter": dict(tpl.get("catalog_filter") or {}),
            }
        )
    return templates


def read_knowledge_file(relative_path: str) -> str:
    """Read a file under knowledge/ after path validation."""
    rel = relative_path.strip().lstrip("/")
    if ".." in rel.split("/"):
        raise ValueError("Invalid knowledge path")
    full = (KNOWLEDGE_ROOT / rel).resolve()
    if not str(full).startswith(str(KNOWLEDGE_ROOT.resolve())):
        raise ValueError("Knowledge path escapes knowledge root")
    if not full.is_file():
        raise FileNotFoundError(f"Knowledge file not found: {relative_path}")
    return full.read_text(encoding="utf-8")


@lru_cache(maxsize=32)
def load_package_briefs_index(template_id: str, index_ref: str) -> dict[str, Any]:
    raw = read_static_block(template_id, index_ref)
    data = yaml.safe_load(raw) or {}
    return data if isinstance(data, dict) else {}


def read_static_block(template_id: str, file_ref: str) -> str:
    rel = file_ref.strip().lstrip("/")
    if ".." in rel.split("/"):
        raise ValueError("Invalid block path")
    base = template_dir(template_id).resolve()
    full = (base / rel).resolve()
    if not str(full).startswith(str(base)):
        raise ValueError("Block path escapes template directory")
    if not full.is_file():
        raise FileNotFoundError(f"Template block not found: {file_ref}")
    return full.read_text(encoding="utf-8")
