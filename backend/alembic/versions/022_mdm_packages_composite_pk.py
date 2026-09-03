"""mdm_packages composite primary key (package_id, bu) + surrogate id

Revision ID: 022
Revises: 021
Create Date: 2026-06-21

Business key is package code scoped by BU. In this schema the code column is
``package_id`` (not ``code``). A UUID ``id`` surrogate remains unique for
downstream relational joins.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "022"
down_revision: Union[str, Sequence[str], None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _constraints(table_name: str) -> set[str]:
    return {constraint["name"] for constraint in sa.inspect(op.get_bind()).get_unique_constraints(table_name)}


def _foreign_keys(table_name: str) -> list[dict]:
    return sa.inspect(op.get_bind()).get_foreign_keys(table_name)


def _drop_package_service_fk_to_packages() -> None:
    for fk in _foreign_keys("mdm_package_services"):
        if fk.get("referred_table") == "mdm_packages" and "package_id" in (fk.get("constrained_columns") or []):
            op.drop_constraint(fk["name"], "mdm_package_services", type_="foreignkey")


def _ensure_package_services_bu() -> None:
    link_columns = _columns("mdm_package_services")
    if "bu" not in link_columns:
        op.add_column("mdm_package_services", sa.Column("bu", sa.String(64), nullable=True))
        op.execute(
            sa.text(
                """
                UPDATE mdm_package_services ps
                SET bu = p.bu
                FROM mdm_packages p
                WHERE ps.package_id = p.package_id
                """
            )
        )
        op.alter_column("mdm_package_services", "bu", nullable=False)

    pk = sa.inspect(op.get_bind()).get_pk_constraint("mdm_package_services")
    pk_columns = pk.get("constrained_columns") or []
    if pk_columns != ["package_id", "bu", "sku"]:
        if pk.get("name"):
            op.drop_constraint(pk["name"], "mdm_package_services", type_="primary")
        op.create_primary_key(
            "mdm_package_services_pkey",
            "mdm_package_services",
            ["package_id", "bu", "sku"],
        )


def upgrade() -> None:
    package_columns = _columns("mdm_packages")
    if "id" not in package_columns:
        op.add_column(
            "mdm_packages",
            sa.Column(
                "id",
                postgresql.UUID(as_uuid=True),
                server_default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
        )

    _ensure_package_services_bu()
    _drop_package_service_fk_to_packages()

    pk = sa.inspect(op.get_bind()).get_pk_constraint("mdm_packages")
    pk_columns = pk.get("constrained_columns") or []
    if pk_columns != ["package_id", "bu"]:
        if pk.get("name"):
            op.drop_constraint(pk["name"], "mdm_packages", type_="primary")
        op.create_primary_key("mdm_packages_pkey", "mdm_packages", ["package_id", "bu"])

    package_constraints = _constraints("mdm_packages")
    if "uq_mdm_packages_id" not in package_constraints:
        op.create_unique_constraint("uq_mdm_packages_id", "mdm_packages", ["id"])

    fk_names = {fk["name"] for fk in _foreign_keys("mdm_package_services")}
    if "mdm_package_services_package_id_bu_fkey" not in fk_names:
        op.create_foreign_key(
            "mdm_package_services_package_id_bu_fkey",
            "mdm_package_services",
            "mdm_packages",
            ["package_id", "bu"],
            ["package_id", "bu"],
            ondelete="CASCADE",
        )


def downgrade() -> None:
    _drop_package_service_fk_to_packages()

    pk = sa.inspect(op.get_bind()).get_pk_constraint("mdm_packages")
    pk_columns = pk.get("constrained_columns") or []
    if pk_columns != ["package_id"]:
        if pk.get("name"):
            op.drop_constraint(pk["name"], "mdm_packages", type_="primary")
        op.create_primary_key("mdm_packages_pkey", "mdm_packages", ["package_id"])

    package_constraints = _constraints("mdm_packages")
    if "uq_mdm_packages_id" in package_constraints:
        op.drop_constraint("uq_mdm_packages_id", "mdm_packages", type_="unique")

    link_pk = sa.inspect(op.get_bind()).get_pk_constraint("mdm_package_services")
    link_pk_columns = link_pk.get("constrained_columns") or []
    if link_pk_columns != ["package_id", "sku"]:
        if link_pk.get("name"):
            op.drop_constraint(link_pk["name"], "mdm_package_services", type_="primary")
        op.create_primary_key("mdm_package_services_pkey", "mdm_package_services", ["package_id", "sku"])

    link_columns = _columns("mdm_package_services")
    if "bu" in link_columns:
        op.drop_column("mdm_package_services", "bu")

    fk_names = {fk["name"] for fk in _foreign_keys("mdm_package_services")}
    if "mdm_package_services_package_id_fkey" not in fk_names:
        op.create_foreign_key(
            "mdm_package_services_package_id_fkey",
            "mdm_package_services",
            "mdm_packages",
            ["package_id"],
            ["package_id"],
            ondelete="CASCADE",
        )

    package_columns = _columns("mdm_packages")
    if "id" in package_columns:
        op.drop_column("mdm_packages", "id")
