"""drop MDM range and structured price spec columns

Revision ID: 016
Revises: 015
Create Date: 2026-06-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "016"
down_revision: Union[str, Sequence[str], None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def upgrade() -> None:
    columns = _columns("mdm_services")
    for column_name in ("price_min", "price_max", "price_spec"):
        if column_name in columns:
            op.drop_column("mdm_services", column_name)


def downgrade() -> None:
    columns = _columns("mdm_services")
    if "price_min" not in columns:
        op.add_column("mdm_services", sa.Column("price_min", sa.Numeric(18, 2), nullable=True))
    if "price_max" not in columns:
        op.add_column("mdm_services", sa.Column("price_max", sa.Numeric(18, 2), nullable=True))
    if "price_spec" not in columns:
        op.add_column(
            "mdm_services",
            sa.Column("price_spec", postgresql.JSONB(), server_default="{}", nullable=False),
        )
