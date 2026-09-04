"""Load the BVI MDM catalog snapshot used by the Alembic seed migration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

DEFAULT_BVI_JSON = Path(__file__).resolve().parent / "data" / "bvi_catalog.json"


@dataclass
class ServiceRecord:
    sku: str
    jurisdiction: str
    bu: str
    department_team: str | None
    service_name: str
    description: str | None
    scope_of_work: str | None
    billing_frequency: str
    recurring: str
    status: str
    pricing_type: str
    price_currency: str
    price_amount: Decimal | None
    fee_raw: str | None
    footnotes: str | None
    sku_semantic_for_ai: str | None


@dataclass
class PackageRecord:
    package_id: str
    jurisdiction: str
    bu: str
    package_name: str
    package_semantic_for_ai: str | None
    linked_skus: list[str]
    status: str = "ACTIVE"


@dataclass
class MdmCatalogSnapshot:
    services: list[ServiceRecord]
    packages: list[PackageRecord]


def _json_to_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def snapshot_from_jsonable(payload: dict[str, Any]) -> MdmCatalogSnapshot:
    services = [
        ServiceRecord(
            **{
                **row,
                "price_amount": _json_to_decimal(row.get("price_amount")),
            }
        )
        for row in payload.get("services") or []
    ]
    packages = [
        PackageRecord(**{k: v for k, v in row.items() if k != "package_detail"})
        for row in payload.get("packages") or []
    ]
    return MdmCatalogSnapshot(services=services, packages=packages)


def load_bvi_catalog_json(path: Path | None = None) -> MdmCatalogSnapshot:
    payload = json.loads((path or DEFAULT_BVI_JSON).read_text(encoding="utf-8"))
    return snapshot_from_jsonable(payload)
