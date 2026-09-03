"""drop mdm_services.product_name and rename service_name_on_proposal to service_name

Revision ID: 020
Revises: 019
Create Date: 2026-06-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: Union[str, Sequence[str], None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    columns = _columns("mdm_services")
    if "service_name_on_proposal" in columns and "service_name" not in columns:
        op.alter_column(
            "mdm_services",
            "service_name_on_proposal",
            new_column_name="service_name",
            existing_type=sa.Text(),
            existing_nullable=False,
        )
    columns = _columns("mdm_services")
    if "product_name" in columns:
        op.drop_column("mdm_services", "product_name")


def downgrade() -> None:
    columns = _columns("mdm_services")
    if "product_name" not in columns:
        op.add_column("mdm_services", sa.Column("product_name", sa.Text(), nullable=True))
        op.execute(sa.text("UPDATE mdm_services SET product_name = service_name WHERE product_name IS NULL"))
        op.alter_column("mdm_services", "product_name", existing_type=sa.Text(), nullable=False)

    columns = _columns("mdm_services")
    if "service_name" in columns and "service_name_on_proposal" not in columns:
        op.alter_column(
            "mdm_services",
            "service_name",
            new_column_name="service_name_on_proposal",
            existing_type=sa.Text(),
            existing_nullable=False,
        )
