from app.tools.builtin import platform_time
from app.tools.diagram import render_plantuml_tool
from app.tools.mdm_catalog import (
    get_mdm_package_services,
    list_mdm_packages,
    list_mdm_packages_for_services,
    search_mdm_services,
)
from app.tools.proposal import (
    add_package_to_proposal_draft,
    add_services_to_proposal_draft,
    enable_proposal_draft_section,
    generate_document,
    generate_word_document,
    get_proposal_draft,
    initialize_proposal_draft,
    list_templates,
    patch_proposal_draft,
    read_knowledge,
    remove_fee_rows_from_proposal_draft,
    render_preview,
)
from app.tools.slide import render_html_ppt_tool, render_slidev_tool
from app.tools.viz import list_sql_results, suggest_visualization
from app.yl_worker2.tools import YL_WORKER2_TOOLS

BUILTIN_TOOLS = {
    "platform_time": platform_time,
    "render_plantuml": render_plantuml_tool,
    "render_slidev": render_slidev_tool,
    "render_html_ppt": render_html_ppt_tool,
    "list_sql_results": list_sql_results,
    "suggest_visualization": suggest_visualization,
    "list_templates": list_templates,
    "list_mdm_packages": list_mdm_packages,
    "get_mdm_package_services": get_mdm_package_services,
    "search_mdm_services": search_mdm_services,
    "list_mdm_packages_for_services": list_mdm_packages_for_services,
    "read_knowledge": read_knowledge,
    "initialize_proposal_draft": initialize_proposal_draft,
    "get_proposal_draft": get_proposal_draft,
    "patch_proposal_draft": patch_proposal_draft,
    "add_package_to_proposal_draft": add_package_to_proposal_draft,
    "add_services_to_proposal_draft": add_services_to_proposal_draft,
    "remove_fee_rows_from_proposal_draft": remove_fee_rows_from_proposal_draft,
    "enable_proposal_draft_section": enable_proposal_draft_section,
    "render_preview": render_preview,
    "generate_document": generate_document,
    "generate_word_document": generate_word_document,
    **YL_WORKER2_TOOLS,
}
