"""Resolve MDM catalog scope (jurisdiction + bu) from template or active proposal draft."""

from __future__ import annotations

from typing import Any

from app.proposal.context import get_run_proposal_state
from app.proposal.loaders import load_template_yaml


class CatalogScopeError(ValueError):
    """Raised when catalog scope cannot be resolved."""


def resolve_catalog_scope(*, template_id: str | None = None) -> dict[str, str]:
    """Return {template_id, jurisdiction, bu} for MDM queries."""
    resolved_template_id = (template_id or "").strip()
    if not resolved_template_id:
        ctx = get_run_proposal_state()
        if ctx and ctx.draft:
            resolved_template_id = str((ctx.draft.get("meta") or {}).get("template_id") or "").strip()

    if not resolved_template_id:
        raise CatalogScopeError(
            "template_id is required when no proposal draft is initialized "
            "(pass template_id or call initialize_proposal_draft first)."
        )

    tpl = load_template_yaml(resolved_template_id)
    if not tpl:
        raise CatalogScopeError(f"Unknown template_id: {resolved_template_id!r}")

    catalog_filter = tpl.get("catalog_filter") or {}
    jurisdiction = str(catalog_filter.get("jurisdiction") or "").strip()
    bu = str(catalog_filter.get("bu") or "").strip()
    if not jurisdiction or not bu:
        raise CatalogScopeError(
            f"Template {resolved_template_id!r} does not define catalog_filter.jurisdiction and bu."
        )

    return {
        "template_id": resolved_template_id,
        "jurisdiction": jurisdiction,
        "bu": bu,
    }


def scope_payload(scope: dict[str, str]) -> dict[str, str]:
    return {
        "template_id": scope["template_id"],
        "jurisdiction": scope["jurisdiction"],
        "bu": scope["bu"],
    }
