from app.tools import BUILTIN_TOOLS


def test_mdm_catalog_tools_registered():
    for name in (
        "list_mdm_packages",
        "get_mdm_package_services",
        "search_mdm_services",
        "list_mdm_packages_for_services",
    ):
        assert name in BUILTIN_TOOLS
