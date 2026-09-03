"""Seed the BVI MDM catalog snapshot for the Alembic migration."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine import Connection
from app.mdm.snapshot_io import MdmCatalogSnapshot

BVI_JURISDICTION = "BVI"
BVI_BU = "Harneys"
BVI_CATEGORY_ID = "harneys-bvi"


def _columns(connection: Connection, table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(connection).get_columns(table_name)}


def _scope_column(columns: set[str]) -> str:
    return "jurisdiction" if "jurisdiction" in columns else "region"


def _insert_statement(table_name: str, row: dict) -> sa.TextClause:
    columns = list(row)
    values = ", ".join(f":{column}" for column in columns)
    statement = sa.text(
        f"""
        INSERT INTO {table_name} ({", ".join(columns)})
        VALUES ({values})
        {"RETURNING id" if table_name == "mdm_services" else ""}
        """
    )
    for key in ("price_spec", "extensions"):
        if key in row:
            statement = statement.bindparams(sa.bindparam(key, type_=postgresql.JSONB))
    return statement


def _service_row(service, columns: set[str]) -> dict:
    row = {
        "sku": service.sku,
        "bu": service.bu,
        "department_team": service.department_team,
        "description": service.description,
        "scope_of_work": service.scope_of_work,
        "billing_frequency": service.billing_frequency,
        "recurring": service.recurring,
        "status": service.status,
        "pricing_type": service.pricing_type,
        "price_currency": service.price_currency,
        "price_amount": service.price_amount,
        "fee_raw": service.fee_raw,
        "footnotes": service.footnotes,
        "sku_semantic_for_ai": service.sku_semantic_for_ai,
    }
    # mdm_services name columns: product_name + service_name_on_proposal (006–019), then service_name (020+).
    name = service.service_name
    if "service_name" in columns:
        row["service_name"] = name
    if "service_name_on_proposal" in columns:
        row["service_name_on_proposal"] = name
    if "product_name" in columns:
        row["product_name"] = name
    row[_scope_column(columns)] = service.jurisdiction
    if "category_id" in columns:
        row["category_id"] = BVI_CATEGORY_ID
    if "service_type" in columns:
        row["service_type"] = "SERVICE"
    if "price_min" in columns:
        row["price_min"] = None
    if "price_max" in columns:
        row["price_max"] = None
    if "price_spec" in columns:
        row["price_spec"] = {}
    if "external_record_id" in columns:
        row["external_record_id"] = None
    if "source_sheet" in columns:
        row["source_sheet"] = None
    if "source_row" in columns:
        row["source_row"] = None
    if "extensions" in columns:
        row["extensions"] = {}
    return {key: value for key, value in row.items() if key in columns}


def _package_row(package, columns: set[str]) -> dict:
    row = {
        "package_id": package.package_id,
        "bu": package.bu,
        "package_name": package.package_name,
        "package_semantic_for_ai": package.package_semantic_for_ai,
        "status": package.status,
    }
    row[_scope_column(columns)] = package.jurisdiction
    if "category_id" in columns:
        row["category_id"] = BVI_CATEGORY_ID
    return {key: value for key, value in row.items() if key in columns}


def _link_insert_statement(columns: set[str]) -> sa.TextClause:
    link_columns = ["package_id", "sku", "service_id"]
    if "category_id" in columns:
        link_columns.insert(1, "category_id")
    return sa.text(
        f"""
        INSERT INTO mdm_package_services ({", ".join(link_columns)})
        VALUES ({", ".join(f":{column}" for column in link_columns)})
        ON CONFLICT ({", ".join(column for column in link_columns if column != "service_id")}) DO NOTHING
        """
    )


def _clear_bvi_catalog(connection: Connection) -> None:
    package_columns = _columns(connection, "mdm_packages")
    service_columns = _columns(connection, "mdm_services")
    package_scope = _scope_column(package_columns)
    service_scope = _scope_column(service_columns)
    connection.execute(
        sa.text(
            f"""
            DELETE FROM mdm_package_services ps
            USING mdm_packages p
            WHERE ps.package_id = p.package_id
              AND p.{package_scope} = :jurisdiction
              AND p.bu = :bu
            """
        ),
        {"jurisdiction": BVI_JURISDICTION, "bu": BVI_BU},
    )
    connection.execute(
        sa.text(f"DELETE FROM mdm_packages WHERE {package_scope} = :jurisdiction AND bu = :bu"),
        {"jurisdiction": BVI_JURISDICTION, "bu": BVI_BU},
    )
    connection.execute(
        sa.text(f"DELETE FROM mdm_services WHERE {service_scope} = :jurisdiction AND bu = :bu"),
        {"jurisdiction": BVI_JURISDICTION, "bu": BVI_BU},
    )


def seed_bvi_catalog_sync(connection: Connection, snapshot: MdmCatalogSnapshot) -> dict[str, int]:
    _clear_bvi_catalog(connection)
    service_columns = _columns(connection, "mdm_services")
    package_columns = _columns(connection, "mdm_packages")
    link_columns = _columns(connection, "mdm_package_services")
    link_insert = _link_insert_statement(link_columns)
    sku_index = {}
    for service in snapshot.services:
        row = _service_row(service, service_columns)
        service_id = connection.execute(_insert_statement("mdm_services", row), row).scalar_one()
        sku_index[(service.jurisdiction, service.bu, service.sku)] = service_id

    for package in snapshot.packages:
        package_row = _package_row(package, package_columns)
        connection.execute(_insert_statement("mdm_packages", package_row), package_row)
        for sku in package.linked_skus:
            service_id = sku_index.get((package.jurisdiction, package.bu, sku))
            if service_id is None:
                continue
            link_row = {"package_id": package.package_id, "sku": sku, "service_id": service_id}
            if "category_id" in link_columns:
                link_row["category_id"] = BVI_CATEGORY_ID
            connection.execute(link_insert, link_row)

    return {
        "services": len(snapshot.services),
        "packages": len(snapshot.packages),
    }
