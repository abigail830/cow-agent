"""Tests for profile skills allowlist."""

from __future__ import annotations

from app.platform.profile_loader import AGENTS_ROOT, load_agent_profile


def test_slide_studio_profile_skills_allowlist() -> None:
    profile = load_agent_profile(AGENTS_ROOT / "slide-studio")
    names = {path.name for path in profile.skill_paths}
    assert names <= {"slidev", "html-ppt"}
    assert len(names) == 1
