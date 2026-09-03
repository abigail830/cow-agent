from app.platform.profile_loader import load_agent_profile
from app.proposal.paths import AGENT_ROOT
from app.tools import BUILTIN_TOOLS
from app.tools.proposal import _coerce_object_list


def test_proposal_composer_profile_loads():
    profile = load_agent_profile(AGENT_ROOT)
    assert profile.slug == "proposal-composer"
    allowed = profile.extra_config.get("allowed_tools") or []
    assert "patch_proposal_draft" in allowed
    assert "search_mdm_services" in allowed
    assert "postgres_query_data" not in allowed


def test_proposal_builtin_tools_registered():
    for name in (
        "list_templates",
        "read_knowledge",
        "list_mdm_packages",
        "get_mdm_package_services",
        "search_mdm_services",
        "list_mdm_packages_for_services",
        "initialize_proposal_draft",
        "get_proposal_draft",
        "patch_proposal_draft",
        "add_package_to_proposal_draft",
        "add_services_to_proposal_draft",
        "remove_fee_rows_from_proposal_draft",
        "enable_proposal_draft_section",
        "render_preview",
        "generate_document",
        "generate_word_document",
    ):
        assert name in BUILTIN_TOOLS


def test_proposal_service_payload_accepts_json_string():
    rows = _coerce_object_list('[{"sku":"CSS23","service_name":"Company Incorporation"}]', "services")
    assert rows == [{"sku": "CSS23", "service_name": "Company Incorporation"}]
