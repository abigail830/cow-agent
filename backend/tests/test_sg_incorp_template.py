
def test_materialize_sg_incorp_draft():
    from app.proposal.draft import materialize_draft
    from app.proposal.placeholders import sync_draft_template_placeholders

    draft = materialize_draft(
        template_id="sg-incorp",
        client={"company_name": "Walkghost LTD", "contract_name": "Sara"},
    )
    draft = sync_draft_template_placeholders(draft)
    assert draft["meta"]["template_id"] == "sg-incorp"
    assert draft["meta"]["title"] == "FEE PROPOSAL - Walkghost LTD"
    ids = [section["id"] for section in draft["document"]["sections"]]
    assert ids == [
        "about_incorp",
        "executive_summary",
        "scope_of_service",
        "solution_and_fees",
        "terms",
        "appendices",
        "first_invoice",
    ]
    executive = next(s for s in draft["document"]["sections"] if s["id"] == "executive_summary")
    assert "Dear Sara," in executive["content"]
    assert "Walkghost LTD" in executive["content"]
    scope = next(s for s in draft["document"]["sections"] if s["id"] == "scope_of_service")
    assert "Walkghost LTD" in scope["content"]
    assert "{{client.company_name}}" not in scope["content"]
    fee = next(s for s in draft["document"]["sections"] if s["id"] == "solution_and_fees")
    assert fee["fee_layout"]["table_style"] == "one_off_recurring"
