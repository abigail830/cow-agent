from app.proposal.draft import build_draft_preview, enable_draft_section, materialize_draft, patch_draft
from app.proposal.fee_row import first_invoice_row_amount, is_adhoc_fee_row
from app.proposal.fee_table import render_first_invoice_table
from tests.proposal_fee_fixtures import make_mdm_fee_row


def _sg_fee_layout():
    draft = materialize_draft(template_id="sg-incorp")
    fee = next(s for s in draft["document"]["sections"] if s["id"] == "solution_and_fees")
    return fee["fee_layout"]


def test_is_adhoc_fee_row_matches_variants():
    row = {
        "display": {"preview_primary": "Ad-hoc secretarial work"},
        "source": {"service_name": "Company secretarial"},
    }
    assert is_adhoc_fee_row(row, {}) is True

    row_ad_hoc = {
        "display": {"preview_primary": "Ad hoc filing"},
        "source": {},
    }
    assert is_adhoc_fee_row(row_ad_hoc, {}) is True

    row_ok = {
        "display": {"preview_primary": "XBRL Services"},
        "source": {"scope_of_work": "Annual XBRL filing"},
    }
    assert is_adhoc_fee_row(row_ok, {}) is False

    row_non_adhoc = {
        "display": {"preview_primary": "Non-adhoc support"},
        "source": {},
    }
    assert is_adhoc_fee_row(row_non_adhoc, {}) is False


def test_first_invoice_row_amount_one_off_plus_recurring():
    layout = _sg_fee_layout()
    row = make_mdm_fee_row(
        {
            "sku": "MIX01",
            "service_name": "Setup plus retainer",
            "scope_of_work": "",
            "price_amount": 500.0,
            "price_currency": "SGD",
            "billing_frequency": "MONTHLY",
            "recurring": "RECURRING",
            "pricing_type": "FIXED",
        },
        template_id="sg-incorp",
    )
    row.setdefault("display", {})
    row["display"]["once_off_display"] = "SGD $200.00"
    row["display"]["recurring_display"] = "SGD $800.00 Monthly"
    assert first_invoice_row_amount(row, layout) == 1000.0


def test_first_invoice_row_amount_recurring_only():
    layout = _sg_fee_layout()
    row = make_mdm_fee_row(
        {
            "sku": "REC01",
            "service_name": "Employee Personal Tax Return",
            "scope_of_work": "",
            "price_amount": 500.0,
            "price_currency": "SGD",
            "billing_frequency": "ONE_TIME",
            "recurring": "ONE_OFF",
            "pricing_type": "FIXED",
        },
        template_id="sg-incorp",
    )
    assert first_invoice_row_amount(row, layout) == 500.0


def test_render_first_invoice_table_totals():
    html = render_first_invoice_table(
        [
            {"label": "XBRL Services", "price": 800.0},
            {"label": "Employee Personal Tax Return", "price": 500.0},
        ],
        currency="SGD",
        tax={"rate": 0.09, "label": "GST", "rate_display": "9%"},
    )
    assert "XBRL Services" in html
    assert "$800.00" in html
    assert "$72.00" in html
    assert "$872.00" in html
    assert "$500.00" in html
    assert "$45.00" in html
    assert "$545.00" in html
    assert "$1,300.00" in html
    assert "$117.00" in html
    assert "$1,417.00" in html


def test_first_invoice_derived_section_in_preview():
    draft = materialize_draft(template_id="sg-incorp")
    fee_idx = next(
        i for i, s in enumerate(draft["document"]["sections"]) if s["id"] == "solution_and_fees"
    )
    draft["document"]["sections"][fee_idx]["tables"] = [
        {
            "id": "pkg1",
            "title": "Standard package",
            "rows": [
                make_mdm_fee_row(
                    {
                        "sku": "XBRL",
                        "service_name": "XBRL Services",
                        "scope_of_work": "",
                        "price_amount": 800.0,
                        "price_currency": "SGD",
                        "billing_frequency": "ONE_TIME",
                        "recurring": "ONE_OFF",
                        "pricing_type": "FIXED",
                    },
                    template_id="sg-incorp",
                ),
                make_mdm_fee_row(
                    {
                        "sku": "TAX01",
                        "service_name": "Employee Personal Tax Return",
                        "scope_of_work": "",
                        "price_amount": 500.0,
                        "price_currency": "SGD",
                        "billing_frequency": "ONE_TIME",
                        "recurring": "ONE_OFF",
                        "pricing_type": "FIXED",
                    },
                    template_id="sg-incorp",
                ),
                make_mdm_fee_row(
                    {
                        "sku": "ADH01",
                        "service_name": "Ad-hoc advisory",
                        "scope_of_work": "",
                        "price_amount": 300.0,
                        "price_currency": "SGD",
                        "billing_frequency": "ONE_TIME",
                        "recurring": "ONE_OFF",
                        "pricing_type": "FIXED",
                    },
                    template_id="sg-incorp",
                ),
            ],
        }
    ]
    draft = enable_draft_section(draft, "first_invoice", enabled=True)
    markdown = build_draft_preview(draft)["markdown"]
    assert "# Estimated first invoice value" in markdown
    assert "XBRL Services" in markdown
    assert "Employee Personal Tax Return" in markdown
    assert "$1,417.00" in markdown
    first_invoice_block = markdown.split("# Estimated first invoice value", 1)[1].split("\n# ", 1)[0]
    assert "Ad-hoc advisory" not in first_invoice_block
    assert "XBRL Services" in first_invoice_block


def test_first_invoice_uses_patched_display_price():
    draft = materialize_draft(template_id="sg-incorp")
    fee_idx = next(
        i for i, s in enumerate(draft["document"]["sections"]) if s["id"] == "solution_and_fees"
    )
    row = make_mdm_fee_row(
        {
            "sku": "XBRL",
            "service_name": "XBRL Services",
            "scope_of_work": "",
            "price_amount": 800.0,
            "price_currency": "SGD",
            "billing_frequency": "ONE_TIME",
            "recurring": "ONE_OFF",
            "pricing_type": "FIXED",
        },
        template_id="sg-incorp",
    )
    draft["document"]["sections"][fee_idx]["tables"] = [
        {"id": "pkg1", "title": "Standard package", "rows": [row]}
    ]
    row_idx = 0
    draft = patch_draft(
        draft,
        [
            {
                "op": "replace",
                "path": f"/document/sections/{fee_idx}/tables/0/rows/{row_idx}/display/once_off_display",
                "value": "SGD $900.00",
            }
        ],
    )
    draft = enable_draft_section(draft, "first_invoice", enabled=True)
    markdown = build_draft_preview(draft)["markdown"]
    assert "$900.00" in markdown
    assert "$81.00" in markdown
    assert "$981.00" in markdown
