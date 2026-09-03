"""move BVI service group labels into names and drop group columns

Revision ID: 019
Revises: 018
Create Date: 2026-06-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: Union[str, Sequence[str], None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table_name)}


def upgrade() -> None:
    columns = _columns("mdm_services")
    if {"service_group", "service_group_display"}.issubset(columns):
        op.execute(
            sa.text(
                """
                UPDATE mdm_services
                SET product_name = service_group,
                    service_name_on_proposal = service_group_display
                WHERE jurisdiction = 'BVI'
                  AND service_group IS NOT NULL
                  AND service_group_display IS NOT NULL
                """
            )
        )

    if "idx_mdm_services_group" in _indexes("mdm_services"):
        op.drop_index("idx_mdm_services_group", table_name="mdm_services")
    columns = _columns("mdm_services")
    if "service_group_display" in columns:
        op.drop_column("mdm_services", "service_group_display")
    if "service_group" in columns:
        op.drop_column("mdm_services", "service_group")


def downgrade() -> None:
    columns = _columns("mdm_services")
    if "service_group" not in columns:
        op.add_column("mdm_services", sa.Column("service_group", sa.String(64), nullable=True))
    if "service_group_display" not in columns:
        op.add_column("mdm_services", sa.Column("service_group_display", sa.String(128), nullable=True))

    op.execute(
        sa.text(
            """
            UPDATE mdm_services
            SET service_group = product_name,
                service_group_display = service_name_on_proposal
            WHERE jurisdiction = 'BVI'
            """
        )
    )
    if "idx_mdm_services_group" not in _indexes("mdm_services"):
        op.create_index("idx_mdm_services_group", "mdm_services", ["jurisdiction", "bu", "service_group"])
