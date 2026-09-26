from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.platform.attachments.gist.prompt import (
    GIST_OUTPUT_EXAMPLE,
    build_gist_user_prompt,
    truncate_markdown_for_gist,
)
from app.platform.attachments.gist.schema import AttachmentGistMetadata, parse_gist_metadata
from app.platform.attachments.gist.service import content_sha256
from app.platform.attachments.gist.scheduler import schedule_attachment_gist, _inflight


def test_parse_gist_metadata_valid():
    raw = '{"abstract": "Revenue grew in Q3.", "tags": ["revenue", "Q3", "growth"]}'
    meta = parse_gist_metadata(raw)
    assert meta is not None
    assert "Revenue" in meta.abstract
    assert len(meta.tags) == 3


def test_parse_gist_metadata_accepts_one_tag():
    raw = '{"abstract": "Hello.", "tags": ["a"]}'
    meta = parse_gist_metadata(raw)
    assert meta is not None
    assert meta.tags == ("a",)


def test_parse_gist_metadata_extracts_embedded_json():
    raw = 'Sure.\n{"abstract": "Summary.", "tags": ["x", "y", "z"]}\n'
    meta = parse_gist_metadata(raw)
    assert meta is not None
    assert meta.abstract == "Summary."


def test_parse_gist_metadata_accepts_comma_separated_tags_string():
    raw = '{"abstract": "Hi.", "tags": "alpha, beta, gamma"}'
    meta = parse_gist_metadata(raw)
    assert meta is not None
    assert len(meta.tags) == 3


def test_to_gist_text_joins_tags():
    meta = AttachmentGistMetadata(abstract="Summary here.", tags=("alpha", "beta", "gamma"))
    text = meta.to_gist_text()
    assert "Summary here." in text
    assert "alpha" in text
    assert "|" in text


def test_truncate_markdown_for_gist():
    long = "a" * 200
    out = truncate_markdown_for_gist(long, max_chars=80)
    assert len(out) <= 80
    assert "truncated" in out


def test_build_gist_user_prompt_includes_fence():
    prompt = build_gist_user_prompt(filename="doc.pdf", mime_type="application/pdf", markdown="body")
    assert "doc.pdf" in prompt
    assert "---" in prompt
    assert "body" in prompt
    assert GIST_OUTPUT_EXAMPLE in prompt
    assert "Example shape:" in prompt


def test_content_sha256_stable():
    assert content_sha256("hello") == content_sha256("hello")
    assert content_sha256("a") != content_sha256("b")


def test_schedule_dedupe_inflight():
    _inflight.clear()
    att_id = uuid.uuid4()

    with patch("app.platform.attachments.gist.scheduler.asyncio.create_task") as mock_task:
        with patch("app.platform.attachments.gist.scheduler.get_settings") as mock_settings:
            mock_settings.return_value.attachment_gist_enabled = True
            schedule_attachment_gist(att_id)
            schedule_attachment_gist(att_id)
            assert mock_task.call_count == 1
    _inflight.discard(att_id)


@pytest.mark.asyncio
async def test_generate_skips_llm_when_gist_sha_matches():
    from app.platform.attachments.gist.service import generate_and_save_attachment_gist

    session = AsyncMock()
    attachment_id = uuid.uuid4()
    with patch("app.platform.attachments.gist.service.get_settings") as mock_settings:
        mock_settings.return_value.attachment_gist_enabled = True
        mock_settings.return_value.attachment_gist_api_key.return_value = "key"
        with patch("app.platform.attachments.gist.service.AttachmentRepository") as repo_cls:
            repo = repo_cls.return_value
            row = AsyncMock()
            row.chat_id = uuid.uuid4()
            row.id = attachment_id
            row.filename = "f.pdf"
            row.mime_type = "application/pdf"
            row.parse_status = "ready"
            row.parsed_artifact_manifest = {"artifacts": {"content_md": {"size_bytes": 1}}}
            row.attachment_role = None
            row.gist = "existing gist"
            row.gist_content_sha256 = content_sha256("content")
            repo.get = AsyncMock(return_value=row)
            with patch("app.platform.attachments.gist.service.load_content_md", return_value="content"):
                with patch("app.platform.attachments.gist.service.UtilityModelRegistry") as reg:
                    ok = await generate_and_save_attachment_gist(session, attachment_id)
                    assert ok is True
                    reg.return_value.complete.assert_not_called()


@pytest.mark.asyncio
async def test_generate_stale_after_llm_skips_save():
    from app.platform.attachments.gist.service import generate_and_save_attachment_gist

    session = AsyncMock()
    attachment_id = uuid.uuid4()
    valid_json = '{"abstract": "Done.", "tags": ["a", "b", "c"]}'
    with patch("app.platform.attachments.gist.service.get_settings") as mock_settings:
        mock_settings.return_value.attachment_gist_enabled = True
        mock_settings.return_value.attachment_gist_api_key.return_value = "key"
        mock_settings.return_value.attachment_gist_max_input_chars = 8000
        mock_settings.return_value.attachment_gist_max_output_tokens = 512
        mock_settings.return_value.attachment_gist_temperature = 0.2
        with patch("app.platform.attachments.gist.service.AttachmentRepository") as repo_cls:
            repo = repo_cls.return_value
            row = AsyncMock()
            row.chat_id = uuid.uuid4()
            row.id = attachment_id
            row.filename = "f.pdf"
            row.mime_type = "application/pdf"
            row.parse_status = "ready"
            row.parsed_artifact_manifest = {"artifacts": {"content_md": {"size_bytes": 1}}}
            row.attachment_role = None
            row.gist = None
            row.gist_content_sha256 = None
            repo.get = AsyncMock(return_value=row)
            repo.save_gist_metadata = AsyncMock()
            with patch(
                "app.platform.attachments.gist.service.load_content_md",
                side_effect=["content", "changed"],
            ):
                with patch("app.platform.attachments.gist.service.UtilityModelRegistry") as reg:
                    reg.return_value.complete = AsyncMock(return_value=valid_json)
                    ok = await generate_and_save_attachment_gist(session, attachment_id)
                    assert ok is False
                    repo.save_gist_metadata.assert_not_called()
