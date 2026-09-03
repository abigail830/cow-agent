from app.mdm.catalog_rows import (
    package_row_to_payload,
    pricing_warnings,
    service_row_to_materializer_payload,
)
from app.mdm.catalog_scope import CatalogScopeError, resolve_catalog_scope
from app.proposal.context import init_run_proposal_state, reset_run_proposal_state
from app.proposal.draft import materialize_draft


def test_service_row_to_materializer_payload_includes_pricing_fields():
    payload = service_row_to_materializer_payload(
        {
            "sku": "AM022",
            "service_name": "AML Officer",
            "description": "Provision of MLRO",
            "scope_of_work": "SOW text",
            "department_team": "Compliance Solutions",
            "pricing_type": "FIXED",
            "price_currency": "USD",
            "price_amount": 200.0,
            "billing_frequency": "ANNUALLY",
            "recurring": "RECURRING",
            "fee_raw": None,
            "footnotes": "optional service",
            "sku_semantic_for_ai": "mlro appointment",
        }
    )
    assert payload["sku"] == "AM022"
    assert payload["department_team"] == "Compliance Solutions"
    assert payload["price_amount"] == 200.0
    assert payload["footnotes"] == "optional service"


def test_pricing_warnings_for_non_fixed_without_fee_raw():
    warnings = pricing_warnings(
        {
            "sku": "X1",
            "pricing_type": "UNIT_RATE",
            "price_amount": None,
            "fee_raw": "",
        }
    )
    assert len(warnings) == 1
    assert "X1" in warnings[0]


def test_resolve_catalog_scope_from_draft():
    reset_run_proposal_state()
    draft = materialize_draft(template_id="harneys-bvi", client={"company_name": "Demo"})
    init_run_proposal_state(initial_draft=draft)
    try:
        scope = resolve_catalog_scope()
        assert scope["template_id"] == "harneys-bvi"
        assert scope["jurisdiction"] == "BVI"
        assert scope["bu"] == "Harneys"
    finally:
        reset_run_proposal_state()


def test_resolve_catalog_scope_requires_template_when_no_draft():
    reset_run_proposal_state()
    try:
        resolve_catalog_scope()
        assert False, "expected CatalogScopeError"
    except CatalogScopeError:
        pass


def test_package_row_to_payload():
    payload = package_row_to_payload(
        {
            "package_id": "PKG006",
            "package_name": "AML Officers appointment",
            "package_semantic_for_ai": "mlro bundle",
        }
    )
    assert payload == {
        "package_id": "PKG006",
        "package_name": "AML Officers appointment",
        "package_semantic_for_ai": "mlro bundle",
    }
