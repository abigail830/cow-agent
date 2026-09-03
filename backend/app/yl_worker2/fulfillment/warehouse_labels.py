"""Map yl_warehouse site_code / site_name to fulfillment logic-warehouse display labels."""

from __future__ import annotations

_SUFFIX = "一盘货仓"


def to_logic_warehouse_label(site_name: str | None) -> str:
    """Normalize warehouse name to fulfillment center logic-warehouse label."""
    name = (site_name or "").strip()
    if not name:
        return ""
    if _SUFFIX in name:
        return name
    if name.endswith("仓"):
        return f"{name}{_SUFFIX}"
    return name
