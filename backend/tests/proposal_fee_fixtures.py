"""Helpers for constructing source/display fee rows in tests."""

from __future__ import annotations

from typing import Any

from app.proposal.draft import _effective_fee_layout, materialize_draft
from app.proposal.fee_row import materialize_mdm_fee_row


def make_mdm_fee_row(
    service: dict[str, Any],
    *,
    template_id: str = "au-advisory",
    package_id: str | None = None,
) -> dict[str, Any]:
    draft = materialize_draft(template_id=template_id)
    fee = next(section for section in draft["document"]["sections"] if section.get("kind") == "fee_section")
    layout = _effective_fee_layout(draft, fee)
    return materialize_mdm_fee_row(service, package_id=package_id, layout=layout)
