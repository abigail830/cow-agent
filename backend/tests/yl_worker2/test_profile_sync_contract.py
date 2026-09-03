"""Ensure yl-worker2 DB profile matches disk (discovery tools + prompt)."""

from pathlib import Path

from app.platform.profile_loader import AGENTS_ROOT, load_agent_profile


def test_yl_worker2_disk_profile_has_discovery_tools():
    profile = load_agent_profile(AGENTS_ROOT / "yl-worker2")
    allowed = set((profile.extra_config or {}).get("allowed_tools") or [])
    required = {
        "list_products",
        "list_warehouses",
        "search_products",
        "search_warehouses",
        "resolve_entity",
        "propose_fulfillment_forms",
        "query_snapshot_catalog",
        "list_sources",
        "describe_table",
        "query_source",
        "follow_ref",
    }
    missing = required - allowed
    assert not missing, f"profile.yaml missing discovery tools: {missing}"


def test_yl_worker2_disk_prompt_covers_ontology_query():
    prompt = Path(AGENTS_ROOT / "yl-worker2" / "system_prompt.md").read_text(encoding="utf-8")
    assert "list_sources" in prompt
    assert "describe_table" in prompt
    assert "query_source" in prompt
    assert "follow_ref" in prompt


def test_yl_worker2_disk_prompt_covers_scheduling_role():
    prompt = Path(AGENTS_ROOT / "yl-worker2" / "system_prompt.md").read_text(encoding="utf-8")
    assert "调度管理组" in prompt
    assert "list_products" in prompt
    assert "没有查询产品目录" in prompt or "没有产品目录" in prompt


def test_yl_worker2_disk_prompt_forbids_refusing_catalog():
    prompt = Path(AGENTS_ROOT / "yl-worker2" / "system_prompt.md").read_text(encoding="utf-8")
    assert "MDM" in prompt or "WMS" in prompt
    assert "必须先调 Tool" in prompt or "必须先调" in prompt
