"""Tests for profile skills allowlist."""

from __future__ import annotations

from app.platform.agent.profile_loader import AGENTS_ROOT, load_agent_profile


def test_content_studio_profile_skills_allowlist() -> None:
    profile = load_agent_profile(AGENTS_ROOT / "content-studio")
    names = {path.name for path in profile.skill_paths}
    assert names <= {"kb-qa", "docx", "pptx", "html-slides"}
    assert len(names) == 4
