"""Generate a sample proposal .docx from a template (local dev / template QA).

Usage:
  cd backend && python scripts/generate_proposal_word.py
  cd backend && python scripts/generate_proposal_word.py -o /tmp/demo.docx
  cd backend && python scripts/generate_proposal_word.py --template sg-incorp --company "Oversee Limited"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.proposal.draft import enable_draft_section, materialize_draft
from app.proposal.export_service import ProposalExportError, generate_proposal_docx, word_template_path
from app.proposal.placeholders import sync_draft_template_placeholders
from app.proposal.word_context import build_word_context, word_export_filename
from app.proposal.word_render import render_word_document
from tests.proposal_fee_fixtures import make_mdm_fee_row


def build_sample_draft(
    *,
    template_id: str,
    company_name: str,
    contract_name: str,
    with_first_invoice: bool,
) -> dict:
    draft = sync_draft_template_placeholders(
        materialize_draft(
            template_id=template_id,
            client={
                "company_name": company_name,
                "contract_name": contract_name,
                "contract_email": f"{contract_name.lower().replace(' ', '')}@example.com",
            },
        )
    )
    fee_idx = next(
        i for i, s in enumerate(draft["document"]["sections"]) if s["id"] == "solution_and_fees"
    )
    draft["document"]["sections"][fee_idx]["tables"] = [
        {
            "id": "accounting",
            "title": "ACCOUNTING AND FINANCE",
            "rows": [
                make_mdm_fee_row(
                    {
                        "sku": "XBRL",
                        "service_name": "XBRL Services",
                        "scope_of_work": "Preparation and filing of XBRL financial statements",
                        "price_amount": 800.0,
                        "price_currency": "SGD",
                        "billing_frequency": "ONE_TIME",
                        "recurring": "ONE_OFF",
                        "pricing_type": "FIXED",
                    },
                    template_id=template_id,
                    package_id="accounting",
                ),
                make_mdm_fee_row(
                    {
                        "sku": "BOOK01",
                        "service_name": "Bookkeeping",
                        "scope_of_work": "Monthly bookkeeping and management accounts",
                        "price_amount": 350.0,
                        "price_currency": "SGD",
                        "billing_frequency": "MONTHLY",
                        "recurring": "RECURRING",
                        "pricing_type": "FIXED",
                    },
                    template_id=template_id,
                    package_id="accounting",
                ),
            ],
        },
        {
            "id": "corpsec",
            "title": "CORPORATE SECRETARIAL",
            "rows": [
                make_mdm_fee_row(
                    {
                        "sku": "INC01",
                        "service_name": "Company incorporation",
                        "scope_of_work": "Incorporation of a Singapore private limited company",
                        "price_amount": 1200.0,
                        "price_currency": "SGD",
                        "billing_frequency": "ONE_TIME",
                        "recurring": "ONE_OFF",
                        "pricing_type": "FIXED",
                    },
                    template_id=template_id,
                    package_id="corpsec",
                ),
            ],
        },
    ]
    if with_first_invoice:
        draft = enable_draft_section(draft, "first_invoice", enabled=True)
    return draft


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a sample proposal Word document.")
    parser.add_argument("--template", default="sg-incorp", help="template_id (default: sg-incorp)")
    parser.add_argument("--company", default="Oversee Limited", help="client company_name")
    parser.add_argument("--contact", default="Sara", help="client contract_name")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output .docx path (default: backend/.run/<filename>)",
    )
    parser.add_argument(
        "--no-first-invoice",
        action="store_true",
        help="do not enable the first invoice section",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="generate even when draft is not ready_to_generate",
    )
    args = parser.parse_args()

    template_path = word_template_path(args.template)
    if template_path is None:
        print(f"FAIL: no Word template for {args.template!r}")
        return 1

    draft = build_sample_draft(
        template_id=args.template,
        company_name=args.company,
        contract_name=args.contact,
        with_first_invoice=not args.no_first_invoice,
    )

    try:
        result = generate_proposal_docx(draft, force=args.force, persist=False)
    except ProposalExportError as exc:
        print(f"FAIL: [{exc.code}] {exc.message}")
        return 1

    docx_bytes = render_word_document(template_path, build_word_context(draft))

    out_dir = Path(__file__).resolve().parents[1] / ".run"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.output or (out_dir / word_export_filename(draft))
    out_path.write_bytes(docx_bytes)

    print(f"OK: {out_path}")
    print(f"     template: {template_path}")
    print(f"     title:    {result['title']}")
    print(f"     size:     {len(docx_bytes):,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
