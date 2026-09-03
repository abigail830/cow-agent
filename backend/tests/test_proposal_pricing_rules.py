import pytest

from app.proposal.draft import add_services_to_draft, build_draft_preview, materialize_draft
from app.proposal.fee_table import format_money
from app.proposal.pricing_rules import (
    FEE_RAW_DISPLAY_TYPES,
    FIXED_PRICING_TYPE,
    coerce_price_amount,
    fee_table_amount_display,
    normalize_pricing_type,
    uses_fee_raw_display,
)


@pytest.mark.parametrize(
    "pricing_type",
    sorted(FEE_RAW_DISPLAY_TYPES),
)
def test_non_fixed_types_use_fee_raw_display(pricing_type: str) -> None:
    assert uses_fee_raw_display(pricing_type)
    text = fee_table_amount_display(
        {
            "pricing_type": pricing_type,
            "amount": 636.0,
            "fee_raw": "636 + 797 disbursements",
            "currency": "USD",
        },
        format_money=format_money,
    )
    assert text == "636 + 797 disbursements"


def test_fixed_uses_price_amount_for_display() -> None:
    text = fee_table_amount_display(
        {
            "pricing_type": FIXED_PRICING_TYPE,
            "amount": 600.0,
            "fee_raw": "600 (legacy note)",
            "currency": "AUD",
        },
        format_money=format_money,
    )
    assert text == "AUD $600.00"


def test_range_without_amount_still_shows_fee_raw() -> None:
    text = fee_table_amount_display(
        {
            "pricing_type": "RANGE",
            "amount": None,
            "fee_raw": "120 - 663",
            "currency": "USD",
        },
        format_money=format_money,
    )
    assert text == "120 - 663"


def test_preview_renders_fee_raw_for_base_plus_and_sums_price_amount() -> None:
    draft = materialize_draft(template_id="harneys-bvi")
    updated = add_services_to_draft(
        draft,
        [
            {
                "sku": "CSS016",
                "service_name": "Annual return filing",
                "pricing_type": "BASE_PLUS",
                "price_currency": "USD",
                "price_amount": 636.0,
                "fee_raw": "636 + 797 disbursements",
                "billing_frequency": "ONE_TIME",
                "recurring": "ONE_OFF",
            }
        ],
    )
    preview = build_draft_preview(updated)
    assert "636 + 797 disbursements" in preview["markdown"]
    assert "USD $636.00" not in preview["markdown"]


def test_preview_renders_fixed_amount() -> None:
    draft = materialize_draft(template_id="au-advisory")
    updated = add_services_to_draft(
        draft,
        [
            {
                "sku": "TA01",
                "service_name": "Application",
                "pricing_type": "FIXED",
                "price_currency": "AUD",
                "price_amount": 600.0,
                "fee_raw": "600",
                "billing_frequency": "ONE_TIME",
                "recurring": "ONE_OFF",
            }
        ],
    )
    preview = build_draft_preview(updated)
    assert "AUD $600.00" in preview["markdown"]


def test_au_frequency_table_shows_fee_raw_in_frequency_column_and_amount_in_total() -> None:
    draft = materialize_draft(template_id="au-advisory")
    updated = add_services_to_draft(
        draft,
        [
            {
                "sku": "ACT01",
                "service_name": "External Actuary Report",
                "pricing_type": "UNIT_RATE",
                "price_currency": "AUD",
                "price_amount": 170.0,
                "fee_raw": "AUD 170/年",
                "billing_frequency": "ANNUALLY",
                "recurring": "RECURRING",
            },
            {
                "sku": "PEN01",
                "service_name": "Pension Paperwork",
                "pricing_type": "UNIT_RATE",
                "price_currency": "AUD",
                "price_amount": 400.0,
                "fee_raw": "400 per pension stream",
                "billing_frequency": "ANNUALLY",
                "recurring": "RECURRING",
            },
        ],
    )
    preview = build_draft_preview(updated)
    assert "AUD 170/年" in preview["markdown"]
    assert "400 per pension stream" in preview["markdown"]
    assert "AUD $170.00" in preview["markdown"]
    assert "AUD $400.00" in preview["markdown"]


def test_au_frequency_table_total_annualizes_monthly_fixed_amount() -> None:
    draft = materialize_draft(template_id="au-advisory")
    updated = add_services_to_draft(
        draft,
        [
            {
                "sku": "FF09",
                "service_name": "Monthly Payroll Processing",
                "pricing_type": "FIXED",
                "price_currency": "AUD",
                "price_amount": 1000.0,
                "fee_raw": "1000",
                "billing_frequency": "MONTHLY",
                "recurring": "RECURRING",
            }
        ],
    )
    preview = build_draft_preview(updated)
    assert "AUD $1,000.00" in preview["markdown"]
    assert "AUD $12,000.00" in preview["markdown"]


def test_materialized_fee_row_stores_fee_raw() -> None:
    draft = materialize_draft(template_id="au-advisory")
    updated = add_services_to_draft(
        draft,
        [
            {
                "sku": "GI01",
                "service_name": "R&D Financing",
                "pricing_type": "UNIT_RATE",
                "price_currency": "AUD",
                "price_amount": 4500.0,
                "fee_raw": "4500 per round of R&D Financing",
                "billing_frequency": "ONE_TIME",
                "recurring": "ONE_OFF",
            }
        ],
    )
    row = updated["document"]["sections"][1]["tables"][0]["rows"][0]
    source = row["source"]
    display = row["display"]
    assert source["price_amount"] == 4500.0
    assert source["fee_raw"] == "4500 per round of R&D Financing"
    assert normalize_pricing_type(source["pricing_type"]) == "UNIT_RATE"
    assert coerce_price_amount(source["price_amount"]) == 4500.0
    assert "4500 per round" in str(display["frequency_columns_display"]["once_off"])
