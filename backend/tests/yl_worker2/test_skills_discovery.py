"""Verify yl-worker2 ontology skill is discoverable."""

from app.platform.profile_loader import AGENTS_ROOT, load_agent_profile


def test_yl_worker2_ontology_core_skill():
    profile = load_agent_profile(AGENTS_ROOT / "yl-worker2")
    skill_names = {p.name for p in profile.skill_paths}
    assert skill_names == {"yl-oip-ontology-core"}
