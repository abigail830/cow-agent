from app.proposal.draft import add_package_to_draft, build_draft_preview, materialize_draft
from app.proposal.footnotes import (
    apply_footnote_numbers,
    collect_footnotes,
    collect_table_footnotes,
    footnote_superscript_html,
    normalize_footnote,
    render_footnotes_footer,
)


def test_normalize_footnote():
    assert normalize_footnote(None) is None
    assert normalize_footnote("") is None
    assert normalize_footnote("  nan  ") is None
    assert normalize_footnote(" optional service ") == "optional service"


def test_collect_footnotes_dedupes_and_orders():
    rows = [
        {"sku": "A", "footnotes": "optional service"},
        {"sku": "B", "footnotes": "Includes FAR filing."},
        {"sku": "C", "footnotes": "optional service"},
    ]
    entries = collect_footnotes(rows)
    assert len(entries) == 2
    assert entries[0].number == 1
    assert entries[0].text == "optional service"
    assert entries[0].skus == ("A", "C")
    assert entries[1].number == 2
    assert entries[1].text == "Includes FAR filing."


def test_render_footnotes_footer_single_numbering():
    rows = [{"sku": "A", "footnotes": "Note one"}]
    html = render_footnotes_footer(collect_table_footnotes(rows))
    assert "proposal-fee-footnotes" in html
    assert 'id="fn-1"' in html
    assert "Note one" in html
    assert "proposal-fee-footnote-num" not in html
    assert "1. 1." not in html


def test_footnote_superscript_links_to_footer():
    assert 'href="#fn-2"' in footnote_superscript_html(2)
    assert "proposal-fee-ref" in footnote_superscript_html(2)


def test_bvi_preview_renders_section_footnotes_once_with_refs():
    draft = materialize_draft(template_id="harneys-bvi")
    updated = add_package_to_draft(
        draft,
        {"package_id": "PKG002", "package_name": "Annual maintenance"},
        [
            {
                "sku": "CSS013",
                "service_name": "Financial Annual Return (FAR)",
                "description": "FAR filing",
                "scope_of_work": "",
                "department_team": "Corporate Services",
                "price_amount": 350.0,
                "price_currency": "USD",
                "billing_frequency": "ANNUALLY",
                "recurring": "RECURRING",
                "pricing_type": "FIXED",
                "footnotes": "Includes collecting and filing the completed FAR.",
            },
            {
                "sku": "CSS015",
                "service_name": "Capital contribution",
                "description": "Optional capital contribution",
                "scope_of_work": "",
                "department_team": "Corporate Services",
                "price_amount": 100.0,
                "price_currency": "USD",
                "billing_frequency": "ONE_TIME",
                "recurring": "ONE_OFF",
                "pricing_type": "FIXED",
                "footnotes": "optional service",
            },
            {
                "sku": "CSS016",
                "service_name": "Redemption or distributions of dividends",
                "description": "Optional redemption",
                "scope_of_work": "",
                "department_team": "Finance Function",
                "price_amount": 100.0,
                "price_currency": "USD",
                "billing_frequency": "ONE_TIME",
                "recurring": "ONE_OFF",
                "pricing_type": "FIXED",
                "footnotes": "optional service",
            },
        ],
    )
    preview = build_draft_preview(updated)
    markdown = preview["markdown"]
    assert markdown.count("proposal-fee-footnotes") == 1
    assert "Includes collecting and filing the completed FAR." in markdown
    assert markdown.count("optional service") == 1
    assert "proposal-fee-ref" in markdown
    assert 'class="proposal-fee-service"' in markdown
    service_cells = markdown.split('class="proposal-fee-service"')[1:]
    assert any("proposal-fee-ref" in cell for cell in service_cells)
    amount_only_cells = markdown.split('class="proposal-fee-amount"')[1:]
    assert not any("proposal-fee-ref" in cell.split("</td>", 1)[0] for cell in amount_only_cells)
    assert markdown.rindex("</tbody></table>") < markdown.index("proposal-fee-footnotes")


def test_apply_footnote_numbers():
    rows = [
        {"footnotes": "optional service"},
        {"footnotes": "Includes FAR filing."},
    ]
    entries = collect_footnotes(rows)
    apply_footnote_numbers(rows, entries)
    assert rows[0]["footnote_num"] == 1
    assert rows[1]["footnote_num"] == 2
