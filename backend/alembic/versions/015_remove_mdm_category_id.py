"""remove proposal category scope from MDM tables

Revision ID: 015
Revises: 014
Create Date: 2026-06-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: Union[str, Sequence[str], None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def _constraints(table_name: str) -> set[str]:
    return {constraint["name"] for constraint in sa.inspect(op.get_bind()).get_unique_constraints(table_name)}


def upgrade() -> None:
    service_columns = _columns("mdm_services")
    package_columns = _columns("mdm_packages")
    link_columns = _columns("mdm_package_services")

    service_indexes = _indexes("mdm_services")
    if "idx_mdm_services_category" in service_indexes:
        op.drop_index("idx_mdm_services_category", table_name="mdm_services")
    if "idx_mdm_services_group" in service_indexes:
        op.drop_index("idx_mdm_services_group", table_name="mdm_services")
    if "idx_mdm_services_scope" not in service_indexes:
        op.create_index("idx_mdm_services_scope", "mdm_services", ["region", "bu"])
    if "idx_mdm_services_group" not in _indexes("mdm_services"):
        op.create_index("idx_mdm_services_group", "mdm_services", ["region", "bu", "service_group"])

    service_constraints = _constraints("mdm_services")
    if "uq_mdm_services_sku_category" in service_constraints:
        op.drop_constraint("uq_mdm_services_sku_category", "mdm_services", type_="unique")
    if "uq_mdm_services_sku_region_bu" not in service_constraints:
        op.create_unique_constraint("uq_mdm_services_sku_region_bu", "mdm_services", ["sku", "region", "bu"])

    package_indexes = _indexes("mdm_packages")
    if "idx_mdm_packages_category" in package_indexes:
        op.drop_index("idx_mdm_packages_category", table_name="mdm_packages")
    if "idx_mdm_packages_scope" not in package_indexes:
        op.create_index("idx_mdm_packages_scope", "mdm_packages", ["region", "bu"])

    if "category_id" in link_columns:
        op.drop_constraint("mdm_package_services_pkey", "mdm_package_services", type_="primary")
        op.drop_column("mdm_package_services", "category_id")
        op.create_primary_key("mdm_package_services_pkey", "mdm_package_services", ["package_id", "sku"])
    if "category_id" in package_columns:
        op.drop_column("mdm_packages", "category_id")
    if "category_id" in service_columns:
        op.drop_column("mdm_services", "category_id")


def downgrade() -> None:
    op.add_column("mdm_services", sa.Column("category_id", sa.String(64), nullable=True))
    op.add_column("mdm_packages", sa.Column("category_id", sa.String(64), nullable=True))
    op.add_column("mdm_package_services", sa.Column("category_id", sa.String(64), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE mdm_services
            SET category_id = CASE
                WHEN region = 'BVI' AND bu = 'Harneys' THEN 'harneys-bvi'
                WHEN region = 'AU' AND bu = 'Incorp' THEN 'au-advisory'
                ELSE lower(region || '-' || bu)
            END
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE mdm_packages
            SET category_id = CASE
                WHEN region = 'BVI' AND bu = 'Harneys' THEN 'harneys-bvi'
                WHEN region = 'AU' AND bu = 'Incorp' THEN 'au-advisory'
                ELSE lower(region || '-' || bu)
            END
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE mdm_package_services ps
            SET category_id = p.category_id
            FROM mdm_packages p
            WHERE p.package_id = ps.package_id
            """
        )
    )

    op.alter_column("mdm_services", "category_id", nullable=False)
    op.alter_column("mdm_packages", "category_id", nullable=False)
    op.alter_column("mdm_package_services", "category_id", nullable=False)

    op.drop_constraint("mdm_package_services_pkey", "mdm_package_services", type_="primary")
    op.create_primary_key("mdm_package_services_pkey", "mdm_package_services", ["package_id", "category_id", "sku"])
    op.drop_constraint("uq_mdm_services_sku_region_bu", "mdm_services", type_="unique")
    op.create_unique_constraint("uq_mdm_services_sku_category", "mdm_services", ["sku", "category_id"])
    op.drop_index("idx_mdm_services_group", table_name="mdm_services")
    op.drop_index("idx_mdm_services_scope", table_name="mdm_services")
    op.create_index("idx_mdm_services_category", "mdm_services", ["category_id"])
    op.create_index("idx_mdm_services_group", "mdm_services", ["category_id", "service_group"])
    op.drop_index("idx_mdm_packages_scope", table_name="mdm_packages")
    op.create_index("idx_mdm_packages_category", "mdm_packages", ["category_id"])
