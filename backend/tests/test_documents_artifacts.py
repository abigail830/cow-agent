from __future__ import annotations

import uuid

from app.api.schemas import DocumentOut
from app.platform.documents.list_helpers import merge_document_pages, parse_artifact_spec, slim_artifact_spec_for_list


def test_slim_artifact_spec_for_list_strips_content():
    spec = {"artifact_id": "art-1", "title": "Deck", "content": "x" * 5000}
    slim = slim_artifact_spec_for_list(spec)
    assert slim["content"] == ""
    assert slim["title"] == "Deck"


def test_parse_artifact_spec_requires_artifact_id():
    assert parse_artifact_spec({"spec": {"title": "No id"}}) is None
    assert parse_artifact_spec({"spec": {"artifact_id": "art-1", "title": "Ok"}}) == {
        "artifact_id": "art-1",
        "title": "Ok",
    }


def test_merge_document_pages_interleaves_by_created_at():
    attachments = [
        DocumentOut(
            source_type="attachment",
            id=uuid.uuid4(),
            chat_id=uuid.uuid4(),
            filename="a.pdf",
            created_at="2026-01-03T00:00:00+00:00",
            agent_id=uuid.uuid4(),
            agent_name="Agent",
        ),
        DocumentOut(
            source_type="attachment",
            id=uuid.uuid4(),
            chat_id=uuid.uuid4(),
            filename="b.pdf",
            created_at="2026-01-01T00:00:00+00:00",
            agent_id=uuid.uuid4(),
            agent_name="Agent",
        ),
    ]
    artifacts = [
        DocumentOut(
            source_type="artifact",
            id=uuid.uuid4(),
            chat_id=uuid.uuid4(),
            filename="diagram.svg",
            created_at="2026-01-02T00:00:00+00:00",
            agent_id=uuid.uuid4(),
            agent_name="Agent",
            artifact_id="art-1",
        ),
    ]
    page = merge_document_pages(attachments, artifacts, offset=1, limit=1)
    assert len(page) == 1
    assert page[0].source_type == "artifact"
    assert page[0].artifact_id == "art-1"


def test_artifact_repository_filter_sql_compiles():
    from sqlalchemy import select

    from app.db.repositories.chat_ui_annotations import ChatUiAnnotationRepository

    user_id = uuid.uuid4()
    repo = ChatUiAnnotationRepository(session=None)  # type: ignore[arg-type]
    ranked = repo._artifact_ranked_subquery(
        user_id,
        q="deck",
        agent_id=uuid.uuid4(),
        artifact_kind="slide_deck",
    )
    stmt = select(ranked.c.annotation_id).where(ranked.c.rn == 1)
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))

    assert "chat_ui_annotations.kind = 'artifact'" in compiled
    assert user_id.hex in compiled
    assert "display" in compiled
    assert "slide_deck" in compiled
