"""drop import metadata and application service type from MDM services

Revision ID: 017
Revises: 016
Create Date: 2026-06-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "017"
down_revision: Union[str, Sequence[str], None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    columns = _columns("mdm_services")
    for column_name in ("external_record_id", "source_sheet", "source_row", "extensions", "service_type"):
        if column_name in columns:
            op.drop_column("mdm_services", column_name)


def downgrade() -> None:
    columns = _columns("mdm_services")
    if "service_type" not in columns:
        op.add_column(
            "mdm_services",
            sa.Column("service_type", sa.String(32), nullable=False, server_default="SERVICE"),
        )
        op.alter_column("mdm_services", "service_type", server_default=None)
    if "external_record_id" not in columns:
        op.add_column("mdm_services", sa.Column("external_record_id", sa.String(64), nullable=True))
    if "source_sheet" not in columns:
        op.add_column("mdm_services", sa.Column("source_sheet", sa.String(64), nullable=True))
    if "source_row" not in columns:
        op.add_column("mdm_services", sa.Column("source_row", sa.Integer(), nullable=True))
    if "extensions" not in columns:
        op.add_column(
            "mdm_services",
            sa.Column("extensions", postgresql.JSONB(), server_default="{}", nullable=False),
        )
