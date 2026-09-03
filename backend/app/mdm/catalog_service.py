"""Read-only MDM catalog queries for proposal composer tools."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.mdm.catalog_rows import (
    package_row_to_payload,
    pricing_warnings,
    service_row_to_materializer_payload,
)
from app.mdm.catalog_scope import CatalogScopeError, resolve_catalog_scope, scope_payload

_SERVICE_COLUMNS = """
    s.sku,
    s.service_name,
    s.description,
    s.scope_of_work,
    s.department_team,
    s.pricing_type,
    s.price_currency,
    s.price_amount,
    s.billing_frequency,
    s.recurring,
    s.fee_raw,
    s.footnotes,
    s.sku_semantic_for_ai
"""

_MAX_ROWS = 200


def _row_mapping(result) -> list[dict[str, Any]]:
    return [dict(row) for row in result.mappings()]


async def list_packages(
    session: AsyncSession,
    scope: dict[str, str],
    *,
    keyword: str | None = None,
    package_ids: list[str] | None = None,
    include_sku_summary: bool = False,
) -> list[dict[str, Any]]:
    clauses = [
        "p.jurisdiction = :jurisdiction",
        "p.bu = :bu",
        "p.status = 'ACTIVE'",
    ]
    params: dict[str, Any] = {
        "jurisdiction": scope["jurisdiction"],
        "bu": scope["bu"],
        "limit": _MAX_ROWS,
    }

    if package_ids:
        clauses.append("p.package_id = ANY(:package_ids)")
        params["package_ids"] = [str(item).strip() for item in package_ids if str(item).strip()]

    if keyword and keyword.strip():
        clauses.append(
            "(p.package_name ILIKE :keyword OR p.package_semantic_for_ai ILIKE :keyword "
            "OR p.package_id ILIKE :keyword)"
        )
        params["keyword"] = f"%{keyword.strip()}%"

    sku_select = ""
    sku_join = ""
    group_by_sql = ""
    if include_sku_summary:
        sku_select = ", COALESCE(array_agg(ps.sku ORDER BY ps.sku) FILTER (WHERE ps.sku IS NOT NULL), ARRAY[]::varchar[]) AS skus"
        sku_join = """
            LEFT JOIN mdm_package_services ps ON ps.package_id = p.package_id
            LEFT JOIN mdm_services s
              ON ps.sku = s.sku
             AND s.jurisdiction = p.jurisdiction
             AND s.bu = p.bu
             AND s.status = 'ACTIVE'
        """
        group_by_sql = "GROUP BY p.package_id, p.package_name, p.package_semantic_for_ai"

    sql = f"""
        SELECT p.package_id, p.package_name, p.package_semantic_for_ai{sku_select}
        FROM mdm_packages p
        {sku_join}
        WHERE {" AND ".join(clauses)}
        {group_by_sql}
        ORDER BY p.package_name
        LIMIT :limit
    """
    rows = _row_mapping(await session.execute(text(sql), params))
    packages: list[dict[str, Any]] = []
    for row in rows:
        payload = package_row_to_payload(row)
        if include_sku_summary:
            skus = row.get("skus") or []
            payload["skus"] = [str(sku) for sku in skus]
            payload["sku_count"] = len(payload["skus"])
        packages.append(payload)
    return packages


async def get_package_services(
    session: AsyncSession,
    scope: dict[str, str],
    package_id: str,
) -> dict[str, Any]:
    package_id = package_id.strip()
    if not package_id:
        raise ValueError("package_id is required")

    package_sql = text(
        """
        SELECT package_id, package_name, package_semantic_for_ai
        FROM mdm_packages
        WHERE jurisdiction = :jurisdiction
          AND bu = :bu
          AND package_id = :package_id
          AND status = 'ACTIVE'
        """
    )
    package_rows = _row_mapping(
        await session.execute(
            package_sql,
            {
                "jurisdiction": scope["jurisdiction"],
                "bu": scope["bu"],
                "package_id": package_id,
            },
        )
    )
    if not package_rows:
        raise ValueError(f"Active package not found in catalog scope: {package_id}")

    services_sql = text(
        f"""
        SELECT {_SERVICE_COLUMNS.strip()}
        FROM mdm_package_services ps
        JOIN mdm_packages p ON p.package_id = ps.package_id
        JOIN mdm_services s
          ON ps.sku = s.sku
         AND s.jurisdiction = p.jurisdiction
         AND s.bu = p.bu
        WHERE p.jurisdiction = :jurisdiction
          AND p.bu = :bu
          AND ps.package_id = :package_id
          AND p.status = 'ACTIVE'
          AND s.status = 'ACTIVE'
        ORDER BY s.department_team NULLS LAST, ps.sku
        LIMIT :limit
        """
    )
    service_rows = _row_mapping(
        await session.execute(
            services_sql,
            {
                "jurisdiction": scope["jurisdiction"],
                "bu": scope["bu"],
                "package_id": package_id,
                "limit": _MAX_ROWS,
            },
        )
    )
    services = [service_row_to_materializer_payload(row) for row in service_rows]
    warnings: list[str] = []
    for service in services:
        warnings.extend(pricing_warnings(service))

    link_rows = _row_mapping(
        await session.execute(
            text(
                """
                SELECT ps.sku
                FROM mdm_package_services ps
                WHERE ps.package_id = :package_id
                ORDER BY ps.sku
                """
            ),
            {"package_id": package_id},
        )
    )
    linked_skus = [str(row["sku"]) for row in link_rows]
    returned_skus = {str(service["sku"]) for service in services}
    missing_skus = [sku for sku in linked_skus if sku not in returned_skus]
    if missing_skus:
        warnings.append(
            "Package links SKU(s) not available as ACTIVE services in catalog scope: "
            + ", ".join(missing_skus)
        )

    return {
        "package": package_row_to_payload(package_rows[0]),
        "services": services,
        "linked_sku_count": len(linked_skus),
        "service_count": len(services),
        "missing_skus": missing_skus,
        "warnings": warnings,
    }


async def search_services(
    session: AsyncSession,
    scope: dict[str, str],
    *,
    skus: list[str] | None = None,
    keyword: str | None = None,
    department_team: str | None = None,
    package_id: str | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    normalized_skus = [str(item).strip() for item in (skus or []) if str(item).strip()]
    keyword = (keyword or "").strip()
    department_team = (department_team or "").strip()
    package_id = (package_id or "").strip()
    row_limit = max(1, min(int(limit), _MAX_ROWS))

    if not normalized_skus and not keyword and not department_team and not package_id:
        raise ValueError("Provide at least one of skus, keyword, department_team, or package_id.")

    clauses = [
        "s.jurisdiction = :jurisdiction",
        "s.bu = :bu",
        "s.status = 'ACTIVE'",
    ]
    params: dict[str, Any] = {
        "jurisdiction": scope["jurisdiction"],
        "bu": scope["bu"],
        "limit": row_limit,
    }

    join_sql = ""
    if package_id:
        join_sql = """
            JOIN mdm_package_services ps ON ps.sku = s.sku
            JOIN mdm_packages p
              ON p.package_id = ps.package_id
             AND p.jurisdiction = s.jurisdiction
             AND p.bu = s.bu
        """
        clauses.extend(["ps.package_id = :package_id", "p.status = 'ACTIVE'"])
        params["package_id"] = package_id

    if normalized_skus:
        clauses.append("s.sku = ANY(:skus)")
        params["skus"] = normalized_skus

    if keyword:
        clauses.append(
            "(s.service_name ILIKE :keyword OR s.sku_semantic_for_ai ILIKE :keyword "
            "OR s.description ILIKE :keyword OR s.sku ILIKE :keyword)"
        )
        params["keyword"] = f"%{keyword}%"

    if department_team:
        clauses.append("s.department_team ILIKE :department_team")
        params["department_team"] = f"%{department_team}%"

    sql = f"""
        SELECT DISTINCT {_SERVICE_COLUMNS.strip()}
        FROM mdm_services s
        {join_sql}
        WHERE {" AND ".join(clauses)}
        ORDER BY s.department_team NULLS LAST, s.sku
        LIMIT :limit
    """
    rows = _row_mapping(await session.execute(text(sql), params))
    services = [service_row_to_materializer_payload(row) for row in rows]
    found_skus = {str(service["sku"]) for service in services}
    not_found_skus = [sku for sku in normalized_skus if sku not in found_skus]
    warnings: list[str] = []
    for service in services:
        warnings.extend(pricing_warnings(service))

    return {
        "services": services,
        "not_found_skus": not_found_skus,
        "warnings": warnings,
    }


async def list_packages_for_services(
    session: AsyncSession,
    scope: dict[str, str],
    skus: list[str],
) -> dict[str, Any]:
    normalized_skus = [str(item).strip() for item in skus if str(item).strip()]
    if not normalized_skus:
        raise ValueError("At least one sku is required.")

    sql = text(
        """
        SELECT ps.sku,
               s.service_name,
               p.package_id,
               p.package_name
        FROM mdm_package_services ps
        JOIN mdm_packages p ON p.package_id = ps.package_id
        JOIN mdm_services s
          ON ps.sku = s.sku
         AND s.jurisdiction = p.jurisdiction
         AND s.bu = p.bu
        WHERE p.jurisdiction = :jurisdiction
          AND p.bu = :bu
          AND ps.sku = ANY(:skus)
          AND p.status = 'ACTIVE'
          AND s.status = 'ACTIVE'
        ORDER BY ps.sku, p.package_name
        """
    )
    rows = _row_mapping(
        await session.execute(
            sql,
            {
                "jurisdiction": scope["jurisdiction"],
                "bu": scope["bu"],
                "skus": normalized_skus,
            },
        )
    )

    by_sku: dict[str, dict[str, Any]] = {}
    for row in rows:
        sku = str(row["sku"])
        entry = by_sku.setdefault(
            sku,
            {
                "sku": sku,
                "service_name": row.get("service_name"),
                "packages": [],
            },
        )
        package = package_row_to_payload(row)
        if not any(item["package_id"] == package["package_id"] for item in entry["packages"]):
            entry["packages"].append(package)

    items: list[dict[str, Any]] = []
    not_found_skus: list[str] = []
    for sku in normalized_skus:
        if sku in by_sku:
            items.append(by_sku[sku])
        else:
            not_found_skus.append(sku)

    return {"items": items, "not_found_skus": not_found_skus}


async def _with_ephemeral_session(coro_factory):
    """Use a dedicated engine per sync catalog call — never the app-wide async pool."""
    settings = get_settings()
    engine = create_async_engine(
        settings.async_database_url,
        connect_args=settings.async_database_connect_args,
        pool_pre_ping=True,
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            return await coro_factory(session)
    finally:
        await engine.dispose()


def run_catalog_query(coro_factory):
    """Run an async catalog query from sync MAF tool handlers."""
    try:
        asyncio.get_running_loop()
        in_async = True
    except RuntimeError:
        in_async = False

    if not in_async:
        return asyncio.run(_with_ephemeral_session(coro_factory))

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(lambda: asyncio.run(_with_ephemeral_session(coro_factory))).result()


def catalog_tool_response(
    *,
    template_id: str | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    scope = resolve_catalog_scope(template_id=template_id)
    return {
        "status": "ok",
        "scope": scope_payload(scope),
        **payload,
    }


def catalog_tool_error(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, CatalogScopeError):
        return {"status": "error", "error": str(exc)}
    return {"status": "error", "error": str(exc) or type(exc).__name__}
