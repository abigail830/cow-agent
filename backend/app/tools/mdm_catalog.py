"""Read-only MDM catalog tools for proposal composer."""

from __future__ import annotations

import logging
from typing import Annotated, Any

from agent_framework import tool

from app.mdm.catalog_scope import CatalogScopeError, resolve_catalog_scope
from app.mdm.catalog_service import (
    catalog_tool_error,
    catalog_tool_response,
    get_package_services,
    list_packages,
    list_packages_for_services,
    run_catalog_query,
    search_services,
)

logger = logging.getLogger(__name__)


@tool(
    name="list_mdm_packages",
    description=(
        "List ACTIVE MDM packages in the proposal template catalog scope "
        "(jurisdiction + bu from template_id or initialized draft). Use to discover "
        "packages or filter by keyword/package_ids. Read-only; does not modify draft. "
        "Pass template_id when proposal draft is not initialized; otherwise scope "
        "defaults to draft meta.template_id. Package is a common bundle shortcut — "
        "services can also be added individually."
    ),
)
def list_mdm_packages(
    template_id: Annotated[
        str | None,
        "Proposal template id (e.g. harneys-bvi). Required when draft is not initialized.",
    ] = None,
    keyword: Annotated[
        str | None,
        "Optional filter on package_id, package_name, or package_semantic_for_ai.",
    ] = None,
    package_ids: Annotated[
        list[str] | None,
        "Optional exact package_id filters.",
    ] = None,
    include_sku_summary: Annotated[
        bool,
        "When true, include skus[] and sku_count per package for discovery.",
    ] = False,
) -> dict[str, Any]:
    try:
        scope = resolve_catalog_scope(template_id=template_id)

        def _query(session):
            return list_packages(
                session,
                scope,
                keyword=keyword,
                package_ids=package_ids,
                include_sku_summary=include_sku_summary,
            )

        packages = run_catalog_query(_query)
        return catalog_tool_response(template_id=template_id, payload={"packages": packages, "count": len(packages)})
    except Exception as exc:
        logger.exception("list_mdm_packages failed")
        return catalog_tool_error(exc)


@tool(
    name="get_mdm_package_services",
    description=(
        "Load one ACTIVE MDM package and all ACTIVE services linked to it in catalog scope. "
        "Returns package metadata plus service rows shaped for add_package_to_proposal_draft "
        "(query only — call add separately after sales confirmation). Read-only. Pass "
        "template_id when proposal draft is not initialized."
    ),
)
def get_mdm_package_services(
    package_id: Annotated[str, "MDM package_id, e.g. PKG006."],
    template_id: Annotated[
        str | None,
        "Proposal template id (e.g. harneys-bvi). Required when draft is not initialized.",
    ] = None,
) -> dict[str, Any]:
    try:
        scope = resolve_catalog_scope(template_id=template_id)

        def _query(session):
            return get_package_services(session, scope, package_id)

        payload = run_catalog_query(_query)
        return catalog_tool_response(template_id=template_id, payload=payload)
    except Exception as exc:
        logger.exception("get_mdm_package_services failed")
        return catalog_tool_error(exc)


@tool(
    name="search_mdm_services",
    description=(
        "Search ACTIVE MDM services in catalog scope by sku list, keyword, department_team, "
        "and/or package_id filter. Returns service rows shaped for "
        "add_services_to_proposal_draft (query only). Service and package are equally valid "
        "paths — pick whichever matches the sale. Read-only. Pass template_id when proposal "
        "draft is not initialized."
    ),
)
def search_mdm_services(
    template_id: Annotated[
        str | None,
        "Proposal template id (e.g. harneys-bvi). Required when draft is not initialized.",
    ] = None,
    skus: Annotated[list[str] | None, "Optional exact SKU list."] = None,
    keyword: Annotated[
        str | None,
        "Optional match on service_name, sku, sku_semantic_for_ai, or description.",
    ] = None,
    department_team: Annotated[str | None, "Optional department_team filter (ILIKE)."] = None,
    package_id: Annotated[str | None, "Optional: restrict to services linked to this package."] = None,
    limit: Annotated[int, "Max rows (default 100, cap 200)."] = 100,
) -> dict[str, Any]:
    try:
        scope = resolve_catalog_scope(template_id=template_id)

        def _query(session):
            return search_services(
                session,
                scope,
                skus=skus,
                keyword=keyword,
                department_team=department_team,
                package_id=package_id,
                limit=limit,
            )

        payload = run_catalog_query(_query)
        return catalog_tool_response(
            template_id=template_id,
            payload={
                **payload,
                "count": len(payload.get("services") or []),
            },
        )
    except Exception as exc:
        logger.exception("search_mdm_services failed")
        return catalog_tool_error(exc)


@tool(
    name="list_mdm_packages_for_services",
    description=(
        "For given SKUs, list which ACTIVE MDM packages include each service in catalog scope. "
        "Use when starting from services to see bundle shortcuts — does not add to draft. "
        "A SKU in multiple packages is informational only; choose package or à-la-carte services "
        "based on the sale, not platform rules. Read-only. Pass template_id when proposal "
        "draft is not initialized."
    ),
)
def list_mdm_packages_for_services(
    skus: Annotated[list[str], "One or more MDM SKUs to look up."],
    template_id: Annotated[
        str | None,
        "Proposal template id (e.g. harneys-bvi). Required when draft is not initialized.",
    ] = None,
) -> dict[str, Any]:
    try:
        scope = resolve_catalog_scope(template_id=template_id)

        def _query(session):
            return list_packages_for_services(session, scope, skus)

        payload = run_catalog_query(_query)
        return catalog_tool_response(template_id=template_id, payload=payload)
    except CatalogScopeError as exc:
        return catalog_tool_error(exc)
    except Exception as exc:
        logger.exception("list_mdm_packages_for_services failed")
        return catalog_tool_error(exc)
