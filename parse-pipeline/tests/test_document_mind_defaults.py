from __future__ import annotations

from parse_pipeline.config import Settings
from parse_pipeline.schemas.job import DocumentMindOptions, JobOptions


def test_document_mind_options_defaults() -> None:
    opts = DocumentMindOptions()
    assert opts.llm_enhancement is True
    assert opts.enhancement_mode == "VLM"
    assert opts.output_formats == ["markdown", "visualLayoutInfo"]


def test_settings_document_mind_defaults() -> None:
    settings = Settings(
        _env_file=None,
        DOCUMENT_MIND_LLM_ENHANCEMENT=True,
        DOCUMENT_MIND_ENHANCEMENT_MODE="VLM",
    )
    assert settings.document_mind_llm_enhancement is True
    assert settings.document_mind_enhancement_mode == "VLM"


def test_job_options_nested_defaults() -> None:
    job_opts = JobOptions()
    assert job_opts.document_mind.llm_enhancement is True
    assert job_opts.document_mind.enhancement_mode == "VLM"
    assert "visualLayoutInfo" in job_opts.document_mind.output_formats
