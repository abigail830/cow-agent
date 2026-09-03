from app.proposal.fee_table import render_frequency_table, render_payment_options_table, format_scope_html


def test_format_scope_html_bullets_after_including():
    html = format_scope_html(
        "Assistance with company incorporation, including: ASIC registration; TFN application; GST registration"
    )
    assert "<ul>" in html
    assert "ASIC registration" in html
    assert "including" in html.lower()


def test_frequency_table_html_keeps_all_rows_together():
    groups = [
        {
            "group_id": "g1",
            "display_name": "Additional services",
            "rows": [
                {
                    "sku": "A",
                    "label": "Lodgement - Special Purpose Annual Financial Statements",
                    "amount": 4500.0,
                    "billing_frequency": "ANNUALLY",
                    "frequency_columns": {
                        "monthly": None,
                        "quarterly": None,
                        "annual": 4500.0,
                        "once_off": None,
                    },
                    "scope_of_work": "Preparation of special purpose financial statements and tax return lodgement.",
                },
                {
                    "sku": "B",
                    "label": "Setup of Xero",
                    "amount": 500.0,
                    "billing_frequency": "ONE_TIME",
                    "frequency_columns": {
                        "monthly": None,
                        "quarterly": None,
                        "annual": None,
                        "once_off": 500.0,
                    },
                },
                {
                    "sku": "C",
                    "label": "Bank Account Set-up",
                    "amount": 1500.0,
                    "billing_frequency": "ONE_TIME",
                    "frequency_columns": {
                        "monthly": None,
                        "quarterly": None,
                        "annual": None,
                        "once_off": 1500.0,
                    },
                },
            ],
        }
    ]
    table = render_frequency_table(groups, currency="AUD", service_columns={
        "service_name": True,
        "description": False,
        "scope_of_work": True,
    })
    assert "proposal-fee-table-frequency" in table
    assert 'width="33.333%"' in table
    assert table.count('width="13.333%"') >= 10
    assert 'proposal-fee-service" style="width:33.333%' in table
    assert "proposal-fee-col-amount" in table
    assert table.count("proposal-fee-service") == 3
    assert "AUD $4,500.00" in table
    assert "Setup of Xero" in table
    assert "Bank Account Set-up" in table
    assert "Preparation of special purpose" in table
    assert "| 1.2 Setup" not in table


def test_payment_options_table_keeps_default_layout():
    table = render_payment_options_table(
        [
            {
                "label": "Payment Option A",
                "rows": [
                    {
                        "label": "Setup of Xero",
                        "monthly": None,
                        "quarterly": None,
                        "annual": None,
                        "once_off": 500.0,
                    }
                ],
            }
        ],
        currency="AUD",
    )
    assert "proposal-payment-table" in table
    assert "proposal-fee-table-frequency" not in table
    assert "colgroup" not in table
    assert "Monthly Fees" in table
    assert 'style="width:60%"' not in table
