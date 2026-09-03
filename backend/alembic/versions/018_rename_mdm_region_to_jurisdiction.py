"""rename MDM region scope to jurisdiction

Revision ID: 018
Revises: 017
Create Date: 2026-06-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: Union[str, Sequence[str], None] = "017"
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

    if "region" in service_columns and "jurisdiction" not in service_columns:
        op.alter_column("mdm_services", "region", new_column_name="jurisdiction", existing_type=sa.String(16))
    if "region" in package_columns and "jurisdiction" not in package_columns:
        op.alter_column("mdm_packages", "region", new_column_name="jurisdiction", existing_type=sa.String(16))

    service_constraints = _constraints("mdm_services")
    if "uq_mdm_services_sku_region_bu" in service_constraints:
        op.drop_constraint("uq_mdm_services_sku_region_bu", "mdm_services", type_="unique")
    if "uq_mdm_services_sku_jurisdiction_bu" not in _constraints("mdm_services"):
        op.create_unique_constraint(
            "uq_mdm_services_sku_jurisdiction_bu",
            "mdm_services",
            ["sku", "jurisdiction", "bu"],
        )

    service_indexes = _indexes("mdm_services")
    if "idx_mdm_services_scope" in service_indexes:
        op.drop_index("idx_mdm_services_scope", table_name="mdm_services")
    if "idx_mdm_services_group" in service_indexes:
        op.drop_index("idx_mdm_services_group", table_name="mdm_services")
    op.create_index("idx_mdm_services_scope", "mdm_services", ["jurisdiction", "bu"])
    op.create_index("idx_mdm_services_group", "mdm_services", ["jurisdiction", "bu", "service_group"])

    package_indexes = _indexes("mdm_packages")
    if "idx_mdm_packages_scope" in package_indexes:
        op.drop_index("idx_mdm_packages_scope", table_name="mdm_packages")
    op.create_index("idx_mdm_packages_scope", "mdm_packages", ["jurisdiction", "bu"])

    op.execute(sa.text("UPDATE mdm_services SET bu = 'Incorp AU' WHERE bu = 'Incorp'"))
    op.execute(sa.text("UPDATE mdm_packages SET bu = 'Incorp AU' WHERE bu = 'Incorp'"))


def downgrade() -> None:
    op.execute(sa.text("UPDATE mdm_services SET bu = 'Incorp' WHERE bu = 'Incorp AU'"))
    op.execute(sa.text("UPDATE mdm_packages SET bu = 'Incorp' WHERE bu = 'Incorp AU'"))

    service_indexes = _indexes("mdm_services")
    if "idx_mdm_services_scope" in service_indexes:
        op.drop_index("idx_mdm_services_scope", table_name="mdm_services")
    if "idx_mdm_services_group" in service_indexes:
        op.drop_index("idx_mdm_services_group", table_name="mdm_services")

    package_indexes = _indexes("mdm_packages")
    if "idx_mdm_packages_scope" in package_indexes:
        op.drop_index("idx_mdm_packages_scope", table_name="mdm_packages")

    service_constraints = _constraints("mdm_services")
    if "uq_mdm_services_sku_jurisdiction_bu" in service_constraints:
        op.drop_constraint("uq_mdm_services_sku_jurisdiction_bu", "mdm_services", type_="unique")

    service_columns = _columns("mdm_services")
    package_columns = _columns("mdm_packages")
    if "jurisdiction" in service_columns and "region" not in service_columns:
        op.alter_column("mdm_services", "jurisdiction", new_column_name="region", existing_type=sa.String(16))
    if "jurisdiction" in package_columns and "region" not in package_columns:
        op.alter_column("mdm_packages", "jurisdiction", new_column_name="region", existing_type=sa.String(16))

    op.create_index("idx_mdm_services_scope", "mdm_services", ["region", "bu"])
    op.create_index("idx_mdm_services_group", "mdm_services", ["region", "bu", "service_group"])
    op.create_index("idx_mdm_packages_scope", "mdm_packages", ["region", "bu"])
    if "uq_mdm_services_sku_region_bu" not in _constraints("mdm_services"):
        op.create_unique_constraint("uq_mdm_services_sku_region_bu", "mdm_services", ["sku", "region", "bu"])
