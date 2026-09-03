from app.proposal.draft import add_package_to_draft, materialize_draft

_PKG = {"package_id": "PKG001", "package_name": "Incorporation"}


def _service(sku: str, amount: float) -> dict:
    return {
        "sku": sku,
        "service_name": f"Service {sku}",
        "description": f"Desc {sku}",
        "department_team": "Corporate Secretarial Services",
        "pricing_type": "FIXED",
        "price_amount": amount,
        "price_currency": "USD",
        "billing_frequency": "ONE_TIME",
        "recurring": "ONE_OFF",
    }


def test_add_package_merges_missing_skus_when_table_exists():
    draft = materialize_draft(template_id="harneys-bvi")
    first_batch = [_service("CSS001", 100.0), _service("CSS002", 200.0)]
    updated = add_package_to_draft(draft, _PKG, first_batch)

    second_batch = [
        _service("CSS001", 100.0),
        _service("CSS002", 200.0),
        _service("CSS003", 300.0),
        _service("CSS004", 400.0),
    ]
    updated = add_package_to_draft(updated, _PKG, second_batch)

    fee = next(s for s in updated["document"]["sections"] if s["kind"] == "fee_section")
    tables = [t for t in fee["tables"] if t["source"]["package_id"] == "PKG001"]
    assert len(tables) == 1
    skus = [row["source"]["sku"] for row in tables[0]["rows"]]
    assert skus == ["CSS001", "CSS002", "CSS003", "CSS004"]


def test_add_package_re_add_with_no_new_skus_is_idempotent():
    draft = materialize_draft(template_id="harneys-bvi")
    services = [_service("CSS001", 100.0), _service("CSS002", 200.0)]
    updated = add_package_to_draft(draft, _PKG, services)
    again = add_package_to_draft(updated, _PKG, services)

    fee = next(s for s in again["document"]["sections"] if s["kind"] == "fee_section")
    table = next(t for t in fee["tables"] if t["source"]["package_id"] == "PKG001")
    assert len(table["rows"]) == 2
