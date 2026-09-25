from __future__ import annotations

import json
import uuid
from unittest.mock import patch

import pytest

from app.platform.doc_retrieval.context import ChatAttachmentIndexEntry, init_doc_retrieval_context, reset_doc_retrieval_context
from app.platform.doc_retrieval.find import find_attachments
from app.platform.doc_retrieval.grep import grep_content
from app.platform.doc_retrieval.read import read_content_slice
from app.platform.doc_retrieval.tools import (
    attachment_find_tool,
    attachment_grep_tool,
    attachment_read_tool,
)


@pytest.fixture(autouse=True)
def _reset_ctx():
    reset_doc_retrieval_context()
    yield
    reset_doc_retrieval_context()


def _sample_library() -> dict[str, ChatAttachmentIndexEntry]:
    att_id = str(uuid.uuid4())
    return {
        att_id: ChatAttachmentIndexEntry(
            attachment_id=att_id,
            filename="annual-report.pdf",
            mime_type="application/pdf",
            kind="pdf",
            parse_status="ready",
            line_count=100,
            page_count=10,
            figure_count=2,
            section_titles=("Intro", "Financials"),
        )
    }


def test_grep_content_finds_lines():
    content = "Alpha\nBeta keyword here\nGamma"
    matches = grep_content(content, "keyword")
    assert len(matches) == 1
    assert matches[0].line == 2


def test_read_content_slice_by_page():
    content = "p1a\np1b\np2a\np2b"
    meta = {
        "pages": [
            {"page": 1, "line_start": 1, "line_end": 2},
            {"page": 2, "line_start": 3, "line_end": 4},
        ]
    }
    result = read_content_slice(content, meta, page=2)
    assert "p2a" in result["content"]
    assert "p1a" not in result["content"]


def test_find_attachments_scores_filename():
    library = _sample_library()
    results = find_attachments(library, "annual report pdf")
    assert len(results) == 1
    assert results[0]["filename"] == "annual-report.pdf"


def test_attachment_tools_with_context():
    chat_id = uuid.uuid4()
    library = _sample_library()
    att_id = next(iter(library))
    init_doc_retrieval_context(chat_id=chat_id, library=library)

    found = attachment_find_tool("annual report")
    assert found["status"] == "ok"
    assert found["candidates"][0]["attachment_id"] == att_id

    content = "Line1\nkeyword match\nLine3"
    meta = {"line_count": 3, "pages": [{"page": 1, "line_start": 1, "line_end": 3}], "sections": []}
    with patch("app.platform.doc_retrieval.tools.load_content_md", return_value=content):
        with patch("app.platform.doc_retrieval.tools.cached_meta", return_value=meta):
            grep_result = attachment_grep_tool(att_id, "keyword")
            assert grep_result["status"] == "ok"
            assert grep_result["match_count"] == 1

            read_result = attachment_read_tool(att_id, page=1)
            assert read_result["status"] == "ok"
            assert "keyword" in read_result["content"]


def test_attachment_tools_support_office_kind():
    chat_id = uuid.uuid4()
    att_id = str(uuid.uuid4())
    library = {
        att_id: ChatAttachmentIndexEntry(
            attachment_id=att_id,
            filename="proposal.docx",
            mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            kind="office",
            parse_status="ready",
            line_count=50,
            page_count=8,
            figure_count=3,
            section_titles=("Executive Summary",),
        )
    }
    init_doc_retrieval_context(chat_id=chat_id, library=library)
    content = "Executive summary\nkeyword in proposal\n"
    meta = {
        "line_count": 2,
        "pages": [{"page": 1, "line_start": 1, "line_end": 2}],
        "sections": [{"id": "s1", "title": "Executive Summary", "line_start": 1, "line_end": 2}],
    }
    with patch("app.platform.doc_retrieval.tools.load_content_md", return_value=content):
        with patch("app.platform.doc_retrieval.tools.cached_meta", return_value=meta):
            grep_result = attachment_grep_tool(att_id, "keyword")
            assert grep_result["status"] == "ok"
            read_result = attachment_read_tool(att_id, line_start=1, line_end=2)
            assert read_result["status"] == "ok"
            assert "keyword" in read_result["content"]
