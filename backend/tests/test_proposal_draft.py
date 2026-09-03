import pytest

from app.proposal.draft import (
    add_package_to_draft,
    add_services_to_draft,
    build_draft_preview,
    enable_draft_section,
    materialize_draft,
    new_collection_markdown_block,
    patch_draft,
    render_draft_markdown,
)
from tests.proposal_fee_fixtures import make_mdm_fee_row


AU_SERVICE = {
    "sku": "TA01",
    "service_name": "Application - Substituted Accounting Period (Standard offer $600 one-off)",
    "scope_of_work": "Application for Substituted Accounting Period.",
    "billing_frequency": "ONE_TIME",
    "recurring": "ONE_OFF",
    "pricing_type": "FIXED",
    "price_currency": "AUD",
    "price_amount": 600.0,
}


def test_materialize_au_draft_from_template_sections():
    draft = materialize_draft(
        template_id="au-advisory",
        client={"company_name": "Walking Limited"},
    )

    assert draft["meta"]["template_id"] == "au-advisory"
    ids = [section["id"] for section in draft["document"]["sections"]]
    assert "introduction" in ids
    assert "solution_and_fees" in ids
    assert "terms" in ids
    payment = next(s for s in draft["document"]["sections"] if s["id"] == "payment_options")
    assert "agent_guidance" in payment
    assert "overrides" in payment["agent_guidance"]
    assert "agent_guidance" not in payment["derivation"]


def test_materialize_draft_includes_optional_client_facts():
    draft = materialize_draft(template_id="au-advisory", client={"company_name": "Walking Limited"})

    assert draft["facts"]["client"] == {
        "company_name": "Walking Limited",
        "short_name": None,
        "address": None,
        "contract_name": None,
        "contract_title": None,
        "contract_email": None,
    }


def test_materialize_bvi_draft_from_template_sections():
    draft = materialize_draft(
        template_id="harneys-bvi",
        client={"company_name": "BVI Demo Ltd"},
    )

    assert draft["meta"]["template_id"] == "harneys-bvi"
    assert draft["meta"]["title"] == "Proposal - BVI Demo Ltd"
    ids = [section["id"] for section in draft["document"]["sections"]]
    assert "introduction" in ids
    assert "solution_and_fees" in ids
    assert "additional_info" in ids
    assert "appendices" in ids
    appendices = next(s for s in draft["document"]["sections"] if s["id"] == "appendices")
    assert appendices["kind"] == "collection"
    assert appendices.get("blocks") == []
    assert appendices.get("collection") == {"child_kind": "markdown_block"}
    required = next(s for s in draft["document"]["sections"] if s["id"] == "required_documents")
    assert "agent_guidance" not in required
    fee = next(s for s in draft["document"]["sections"] if s["id"] == "solution_and_fees")
    assert "intro" not in fee


def test_materialize_copies_section_agent_guidance():
    from app.proposal.draft import _collection_section

    section = _collection_section(
        {
            "id": "appendices",
            "title": "Appendices",
            "agent_guidance": "Each block title must start with Appendix.",
            "collection": {"child_kind": "markdown_block"},
        }
    )
    assert section["agent_guidance"] == "Each block title must start with Appendix."


def test_materialize_skips_blank_section_agent_guidance():
    from app.proposal.draft import _collection_section

    section = _collection_section(
        {
            "id": "appendices",
            "title": "Appendices",
            "agent_guidance": "   ",
            "collection": {"child_kind": "markdown_block"},
        }
    )
    assert "agent_guidance" not in section


def test_materialize_au_fee_section_intro_is_markdown_block():
    draft = materialize_draft(template_id="au-advisory")
    fee = next(s for s in draft["document"]["sections"] if s["id"] == "solution_and_fees")
    intro = fee["intro"]
    assert intro["kind"] == "markdown_block"
    assert intro["id"] == "intro"
    assert intro["edit_state"] == {"content": "source"}
    assert intro["policy"]["editable"] is True
    assert "professional fees" in intro["content"].lower()


def test_add_package_materializes_editable_fee_rows():
    draft = materialize_draft(template_id="au-advisory")
    updated = add_package_to_draft(
        draft,
        {"package_id": "PKG-AU-1", "package_name": "Tax Package 2"},
        [AU_SERVICE],
    )

    fee = next(s for s in updated["document"]["sections"] if s["kind"] == "fee_section")
    row = fee["tables"][0]["rows"][0]
    assert fee["tables"][0]["title"] == "Tax Package 2"
    assert row["display"]["preview_primary"] == "Application - Substituted Accounting Period"
    assert row["source"]["price_amount"] == 600.0


def test_add_services_materializes_multiple_rows_atomically():
    draft = materialize_draft(template_id="au-advisory")
    second_service = {
        **AU_SERVICE,
        "sku": "CSS23",
        "service_name": "Company Incorporation",
        "price_amount": 1500.0,
    }

    updated = add_services_to_draft(draft, [AU_SERVICE, second_service])

    fee = next(s for s in updated["document"]["sections"] if s["kind"] == "fee_section")
    rows = fee["tables"][0]["rows"]
    assert [row["source"]["sku"] for row in rows] == ["TA01", "CSS23"]
    assert rows[1]["source"]["price_amount"] == 1500.0


def test_patch_draft_updates_display_row_and_preview():
    draft = materialize_draft(template_id="au-advisory")
    fee = next(s for s in draft["document"]["sections"] if s["kind"] == "fee_section")
    row = make_mdm_fee_row(
        {
            **AU_SERVICE,
            "service_name": "Old name",
            "price_amount": 500.0,
        }
    )
    row["display"] = {
        **row["display"],
        "preview_primary": "Old name",
    }
    fee["tables"] = [
        {
            "id": "table_1",
            "title": "Services",
            "rows": [row],
        }
    ]

    updated = patch_draft(
        draft,
        [
            {
                "op": "replace",
                "path": "/document/sections/1/tables/0/rows/0/display/preview_primary",
                "value": "Application - Substituted Accounting Period",
            },
            {
                "op": "replace",
                "path": "/document/sections/1/tables/0/rows/0/display/frequency_columns_display/once_off",
                "value": "AUD $600.00",
            },
            {
                "op": "replace",
                "path": "/document/sections/1/tables/0/rows/0/display/total_display",
                "value": "AUD $600.00",
            },
        ],
    )
    preview = build_draft_preview(updated)
    assert "Application - Substituted Accounting Period" in preview["markdown"]
    assert "Old name" not in preview["markdown"]
    assert "AUD $600.00" in preview["markdown"]


def test_payment_options_derived_from_fee_tables_when_enabled():
    draft = materialize_draft(template_id="au-advisory")
    fee = next(s for s in draft["document"]["sections"] if s["kind"] == "fee_section")
    fee["tables"] = [
        {
            "id": "table_setup",
            "title": "Setup of Xero",
            "rows": [
                make_mdm_fee_row(
                    {
                        "sku": "XERO",
                        "service_name": "Setup of Xero",
                        "scope_of_work": "",
                        "price_amount": 500.0,
                        "price_currency": "AUD",
                        "billing_frequency": "ONE_TIME",
                        "recurring": "ONE_OFF",
                        "pricing_type": "FIXED",
                    }
                )
            ],
        },
        {
            "id": "table_tax",
            "title": "Tax Package 2",
            "rows": [
                make_mdm_fee_row(
                    {
                        **AU_SERVICE,
                        "service_name": "Application",
                        "scope_of_work": "",
                        "price_amount": 400.0,
                        "billing_frequency": "MONTHLY",
                        "recurring": "RECURRING",
                    }
                )
            ],
        },
    ]

    disabled_preview = build_draft_preview(draft)
    assert "# Fee summary" not in disabled_preview["markdown"]

    enabled = enable_draft_section(draft, "payment_options")
    preview = build_draft_preview(enabled)
    assert "# Fee summary" in preview["markdown"]
    assert "Payment Option A" in preview["markdown"]
    assert "Setup of Xero" in preview["markdown"]
    assert "Tax Package 2" in preview["markdown"]
    assert "AUD $500.00" in preview["markdown"]
    assert "AUD $4,800.00" in preview["markdown"]


def test_payment_options_render_multiple_configured_options():
    draft = materialize_draft(template_id="au-advisory")
    fee = next(s for s in draft["document"]["sections"] if s["kind"] == "fee_section")
    fee["tables"] = [
        {
            "id": "table_css",
            "title": "CSS Package 2",
            "rows": [
                make_mdm_fee_row(
                    {
                        "sku": "COMPANY",
                        "service_name": "Company Incorporation",
                        "scope_of_work": "",
                        "price_amount": 2500.0,
                        "price_currency": "AUD",
                        "billing_frequency": "ONE_TIME",
                        "recurring": "ONE_OFF",
                        "pricing_type": "FIXED",
                    }
                ),
                make_mdm_fee_row(
                    {
                        "sku": "AUDIT",
                        "service_name": "Application for Audit Relief",
                        "scope_of_work": "",
                        "price_amount": 900.0,
                        "price_currency": "AUD",
                        "billing_frequency": "ONE_TIME",
                        "recurring": "ONE_OFF",
                        "pricing_type": "FIXED",
                    }
                ),
            ],
        }
    ]
    payment = next(s for s in draft["document"]["sections"] if s["id"] == "payment_options")
    payment["enabled"] = True
    payment["options"] = [
        {
            "option_id": "option_a",
            "label": "Payment Option A - One-off Payment",
            "rows": [
                {
                    "group_id": "table_css",
                    "label": "CSS Package 2",
                    "once_off": 2500.0,
                    "monthly": 0.0,
                    "quarterly": 0.0,
                    "annual": 0.0,
                }
            ],
        },
        {
            "option_id": "option_b",
            "label": "Payment Option B - Monthly Recurring",
            "rows": [
                {
                    "group_id": "table_css",
                    "label": "CSS Package 2",
                    "once_off": 0.0,
                    "monthly": 200.0,
                    "quarterly": 0.0,
                    "annual": 0.0,
                }
            ],
        },
    ]

    preview = build_draft_preview(draft)
    assert "Payment Option A - One-off Payment" in preview["markdown"]
    assert "Payment Option B - Monthly Recurring" in preview["markdown"]
    assert "AUD $2,400.00" in preview["markdown"]


def test_payment_options_render_override_only_options():
    draft = materialize_draft(template_id="au-advisory")
    fee = next(s for s in draft["document"]["sections"] if s["kind"] == "fee_section")
    fee["tables"] = [
        {
            "id": "table_css",
            "title": "CSS Package 2",
            "rows": [
                make_mdm_fee_row(
                    {
                        "sku": "COMPANY",
                        "service_name": "Company Incorporation",
                        "scope_of_work": "",
                        "price_amount": 2500.0,
                        "price_currency": "AUD",
                        "billing_frequency": "ONE_TIME",
                        "recurring": "ONE_OFF",
                        "pricing_type": "FIXED",
                    }
                )
            ],
        }
    ]
    payment = next(s for s in draft["document"]["sections"] if s["id"] == "payment_options")
    payment["enabled"] = True
    payment["overrides"] = {
        "option_a": {
            "label": "Option A — One-off Payment",
            "rows": [
                {
                    "sku": "COMPANY",
                    "service_name": "Company Incorporation",
                    "price": {"amount": 2500.0, "currency": "AUD", "frequency": "ONE_TIME"},
                },
                {
                    "sku": "AUDIT",
                    "service_name": "Application for Audit Relief",
                    "price": {"amount": 900.0, "currency": "AUD", "frequency": "ONE_TIME"},
                }
            ],
        },
        "option_b": {
            "label": "Option B — Monthly Recurring",
            "rows": [
                {
                    "sku": "COMPANY",
                    "service_name": "Company Incorporation",
                    "price": {"amount": 200.0, "currency": "AUD", "frequency": "MONTHLY"},
                },
                {
                    "sku": "AUDIT",
                    "service_name": "Application for Audit Relief",
                    "price": {"amount": 70.0, "currency": "AUD", "frequency": "MONTHLY"},
                }
            ],
        },
    }

    preview = build_draft_preview(draft)
    payment_markdown = preview["markdown"].split("# Fee summary", 1)[1]
    assert "Option A — One-off Payment" in payment_markdown
    assert "Option B — Monthly Recurring" in payment_markdown
    assert "CSS Package 2" in payment_markdown
    assert "Company Incorporation" not in payment_markdown
    assert "Application for Audit Relief" not in payment_markdown
    assert "AUD $3,400.00" in payment_markdown
    assert "AUD $3,240.00" in payment_markdown


def test_payment_options_annualizes_mixed_unit_rate_and_monthly_services() -> None:
    draft = materialize_draft(template_id="au-advisory")
    fee = next(s for s in draft["document"]["sections"] if s["kind"] == "fee_section")
    fee["tables"] = [
        {
            "id": "table_additional_services",
            "title": "Additional Services",
            "rows": [
                make_mdm_fee_row(
                    {
                        "sku": "PEN01",
                        "service_name": "Pension Paperwork",
                        "scope_of_work": "",
                        "price_amount": 400.0,
                        "fee_raw": "400 per pension stream",
                        "price_currency": "AUD",
                        "billing_frequency": "ANNUALLY",
                        "recurring": "RECURRING",
                        "pricing_type": "UNIT_RATE",
                    }
                ),
                make_mdm_fee_row(
                    {
                        "sku": "FF09",
                        "service_name": "Monthly Payroll Processing",
                        "scope_of_work": "",
                        "price_amount": 1000.0,
                        "fee_raw": "1000",
                        "price_currency": "AUD",
                        "billing_frequency": "MONTHLY",
                        "recurring": "RECURRING",
                        "pricing_type": "FIXED",
                    }
                ),
            ],
        }
    ]
    enabled = enable_draft_section(draft, "payment_options")
    preview = build_draft_preview(enabled)

    fee_section = preview["markdown"].split("# Solution and professional fees", 1)[1].split("# Fee summary", 1)[0]
    payment_section = preview["markdown"].split("# Fee summary", 1)[1]

    assert "400 per pension stream" in fee_section
    assert "AUD $12,000.00" in fee_section
    assert "AUD $12,400.00" in payment_section


def test_au_frequency_table_includes_scope_of_work_from_layout() -> None:
    draft = materialize_draft(template_id="au-advisory")
    fee = next(s for s in draft["document"]["sections"] if s["kind"] == "fee_section")
    assert fee["fee_layout"]["service_columns"]["scope_of_work"] is True
    fee["tables"] = [
        {
            "id": "table_smsf",
            "title": "SMSF Services",
            "rows": [
                make_mdm_fee_row(
                    {
                        "sku": "SETUP",
                        "service_name": "Setup - SMSF",
                        "scope_of_work": "Establish SMSF deed and register with the ATO.",
                        "price_amount": 3500.0,
                        "price_currency": "AUD",
                        "billing_frequency": "ONE_TIME",
                        "recurring": "ONE_OFF",
                        "pricing_type": "FIXED",
                    }
                )
            ],
        }
    ]
    preview = build_draft_preview(draft)
    assert "Establish SMSF deed and register with the ATO." in preview["markdown"]


def test_static_sections_render_template_titles_once():
    draft = materialize_draft(template_id="au-advisory")
    preview = build_draft_preview(draft)

    assert "# About Incorp" in preview["markdown"]
    assert "# Terms and conditions" in preview["markdown"]
    assert preview["markdown"].count("# About Incorp") == 1
    assert preview["markdown"].count("# Terms and conditions") == 1


def test_appendices_collection_renders_each_block_as_chapter():
    draft = materialize_draft(template_id="harneys-bvi")
    draft = enable_draft_section(draft, "appendices", enabled=True)
    appendices_idx = next(
        i for i, s in enumerate(draft["document"]["sections"]) if s["id"] == "appendices"
    )
    draft = patch_draft(
        draft,
        [
            {
                "op": "add",
                "path": f"/document/sections/{appendices_idx}/blocks/-",
                "value": new_collection_markdown_block(
                    block_id="appendix-a",
                    title="Appendix A — Sample",
                    content="First appendix body.",
                    edit_state="agent",
                ),
            },
            {
                "op": "add",
                "path": f"/document/sections/{appendices_idx}/blocks/-",
                "value": new_collection_markdown_block(
                    block_id="appendix-b",
                    title="Appendix B — Other",
                    content="Second appendix body.",
                    edit_state="agent",
                ),
            },
        ],
    )
    markdown = render_draft_markdown(draft)
    assert "# Appendix A — Sample\n\nFirst appendix body." in markdown
    assert "# Appendix B — Other\n\nSecond appendix body." in markdown
    assert "# Appendices\n\n" not in markdown
    assert markdown.index("Appendix A") < markdown.index("Appendix B")


def test_new_collection_markdown_block_requires_title():
    with pytest.raises(ValueError, match="title"):
        new_collection_markdown_block(block_id="x", title="")
