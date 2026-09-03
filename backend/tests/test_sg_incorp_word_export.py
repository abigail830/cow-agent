"""Integration test against the real sg-incorp Word template (when present)."""

import re
import zipfile
from io import BytesIO
from pathlib import Path

import pytest

from app.proposal.draft import materialize_draft
from app.proposal.export_service import generate_proposal_docx, word_template_path
from app.proposal.placeholders import sync_draft_template_placeholders
from app.proposal.word_context import build_word_context, word_export_filename
from app.proposal.word_render import render_word_document

REAL_TEMPLATE = word_template_path("sg-incorp")


@pytest.mark.skipif(REAL_TEMPLATE is None, reason="sg-incorp export/proposal.docx not present")
def test_render_real_sg_incorp_proposal_docx():
    from app.proposal.loaders import load_template_yaml

    load_template_yaml.cache_clear()
    draft = sync_draft_template_placeholders(
        materialize_draft(
            template_id="sg-incorp",
            client={
                "company_name": "Walkghost LTD",
                "contract_name": "Sara",
                "contract_email": "sara@example.com",
            },
        )
    )
    context = build_word_context(draft)
    output = render_word_document(REAL_TEMPLATE, context)
    assert output.startswith(b"PK")
    assert len(output) > 10_000

    with zipfile.ZipFile(BytesIO(output)) as zout:
        xml = zout.read("word/document.xml").decode("utf-8")
    assert "<w:p><w:p" not in xml
    assert re.search(r"<w:t[^>]*>[^<]*<w:r", xml) is None

    result = generate_proposal_docx(draft, force=False, persist=False)
    assert result["status"] == "ok"
    assert result["filename"] == word_export_filename(draft)
    assert result["filename"].endswith(".docx")
