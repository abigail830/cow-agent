from app.proposal.draft import add_package_to_draft, build_draft_preview, materialize_draft
from app.proposal.placeholders import sync_draft_template_placeholders


def _pkg003_service():
    return {
        "sku": "AM001",
        "description": "Formation fee",
        "department_team": "Corporate Secretarial Services",
        "pricing_type": "FIXED",
        "price_amount": 100.0,
        "price_currency": "USD",
        "billing_frequency": "ONE_TIME",
        "recurring": "ONE_OFF",
    }


def test_introduction_placeholders_resolve_client_and_packages():
    draft = materialize_draft(
        template_id="harneys-bvi",
        client={"contract_name": "Jane Doe"},
    )
    updated = add_package_to_draft(
        draft,
        {"package_id": "PKG003", "package_name": "Approval Manager"},
        [_pkg003_service()],
    )
    intro = next(s for s in updated["document"]["sections"] if s["id"] == "introduction")
    assert "Jane Doe" in intro["content"]
    assert "- Approval Manager" in intro["content"]
    assert "{{client.contract_name}}" not in intro["content"]
    assert "{{selected_packages_bullet_list}}" not in intro["content"]


def test_package_brief_renders_in_fee_section():
    draft = materialize_draft(template_id="harneys-bvi")
    updated = add_package_to_draft(
        draft,
        {"package_id": "PKG003", "package_name": "Approval Manager"},
        [_pkg003_service()],
    )
    markdown = build_draft_preview(updated)["markdown"]
    assert "## Approved Manager" in markdown
    assert "streamlined route for investment managers" in markdown


def test_fee_tables_heading_separates_briefs_from_tables():
    draft = materialize_draft(template_id="harneys-bvi")
    updated = add_package_to_draft(
        draft,
        {"package_id": "PKG003", "package_name": "Approval Manager"},
        [_pkg003_service()],
    )
    markdown = build_draft_preview(updated)["markdown"]
    solution = markdown.split("# Solution and pricing", 1)[1]
    assert "## Fees" in solution
    assert solution.index("streamlined route for investment managers") < solution.index("## Fees")
    assert solution.index("## Fees") < solution.index("### Approval Manager")


def test_add_package_materializes_table_brief():
    draft = materialize_draft(template_id="harneys-bvi")
    updated = add_package_to_draft(
        draft,
        {"package_id": "PKG003", "package_name": "Approval Manager"},
        [_pkg003_service()],
    )
    fee = next(s for s in updated["document"]["sections"] if s["kind"] == "fee_section")
    table = fee["tables"][0]
    assert table["kind"] == "fee_table"
    brief = table["brief"]
    assert brief["kind"] == "markdown_block"
    assert "streamlined route for investment managers" in brief["content"]


def test_table_reorder_updates_brief_order():
    draft = materialize_draft(template_id="harneys-bvi")
    updated = add_package_to_draft(
        draft,
        {"package_id": "PKG003", "package_name": "Approval Manager"},
        [_pkg003_service()],
    )
    updated = add_package_to_draft(
        updated,
        {"package_id": "PKG001", "package_name": "Incorporation"},
        [
            {
                "sku": "INC001",
                "description": "Incorporation fee",
                "department_team": "Corporate Secretarial Services",
                "pricing_type": "FIXED",
                "price_amount": 200.0,
                "price_currency": "USD",
                "billing_frequency": "ONE_TIME",
                "recurring": "ONE_OFF",
            },
        ],
    )
    fee = next(s for s in updated["document"]["sections"] if s["kind"] == "fee_section")
    fee["tables"] = list(reversed(fee["tables"]))
    markdown = build_draft_preview(updated)["markdown"]
    solution = markdown.split("# Solution and pricing", 1)[1]
    assert solution.index("The set-up cost includes") < solution.index("streamlined route for investment managers")


def test_sync_after_client_patch():
    draft = materialize_draft(template_id="harneys-bvi")
    draft = sync_draft_template_placeholders(draft)
    draft["facts"]["client"]["contract_name"] = "Updated Name"
    draft = sync_draft_template_placeholders(draft)
    intro = next(s for s in draft["document"]["sections"] if s["id"] == "introduction")
    assert "Updated Name" in intro["content"]
