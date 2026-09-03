from app.proposal.loaders import load_template_yaml, load_templates


def test_load_templates():
    templates = load_templates()
    ids = {row["template_id"] for row in templates}
    assert "harneys-bvi" in ids
    assert "au-advisory" in ids
    assert "sg-incorp" in ids


def test_template_declares_catalog_filter():
    tpl = load_template_yaml("harneys-bvi")
    assert tpl["catalog_filter"] == {"jurisdiction": "BVI", "bu": "Harneys"}


def test_harneys_template_has_solution_and_price():
    tpl = load_template_yaml("harneys-bvi")
    sections = {section["id"]: section for section in tpl.get("sections") or []}
    assert "solution_and_fees" in sections
    assert sections["solution_and_fees"]["kind"] == "fee_section"
    layout = sections["solution_and_fees"]["fee_layout"]
    assert layout.get("group_by") == "department"
    assert layout.get("footnotes") == "aggregate"
    cols = layout.get("service_columns") or {}
    assert cols.get("service_name") is False
    assert cols.get("description") is True
    assert cols.get("scope_of_work") is False


def test_au_template_fee_layout():
    tpl = load_template_yaml("au-advisory")
    sections = {section["id"]: section for section in tpl.get("sections") or []}
    layout = sections["solution_and_fees"]["fee_layout"]
    assert layout.get("group_by") == "package"
    assert layout.get("table_style") == "frequency_columns"
    cols = layout.get("service_columns") or {}
    assert cols.get("service_name") is True
    assert cols.get("description") is False
    assert cols.get("scope_of_work") is True
    assert "body" not in tpl
    assert tpl.get("document_title", {}).get("prefix") == "INCORP ADVISORY PROPOSAL"


def test_sg_template_sections_and_fee_layout():
    tpl = load_template_yaml("sg-incorp")
    assert tpl["catalog_filter"] == {"jurisdiction": "SG", "bu": "Incorp SG"}
    sections = {section["id"]: section for section in tpl.get("sections") or []}
    assert sections["about_incorp"]["kind"] == "static_block"
    assert sections["executive_summary"]["kind"] == "markdown_block"
    assert sections["scope_of_service"]["kind"] == "markdown_block"
    layout = sections["solution_and_fees"]["fee_layout"]
    assert layout.get("group_by") == "package"
    assert layout.get("table_style") == "one_off_recurring"
    assert layout.get("currency") == "SGD"
    assert layout.get("footnotes") == "aggregate"
    first_invoice = sections["first_invoice"]
    assert first_invoice["kind"] == "derived_section"
    assert first_invoice["derivation"]["type"] == "first_invoice_from_fee_tables"
    assert first_invoice["derivation"]["tax"]["rate"] == 0.09
    assert tpl.get("document_title", {}).get("prefix") == "FEE PROPOSAL"

