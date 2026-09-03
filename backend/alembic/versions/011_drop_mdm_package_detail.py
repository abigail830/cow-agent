"""drop mdm_packages.package_detail

Revision ID: 011
Revises: 010
Create Date: 2026-06-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, Sequence[str], None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    columns = {col["name"] for col in inspector.get_columns("mdm_packages")}
    if "package_detail" not in columns:
        return

    connection.execute(
        sa.text(
            """
            UPDATE mdm_packages
            SET package_semantic_for_ai = COALESCE(
                NULLIF(btrim(package_detail), ''),
                package_semantic_for_ai,
                package_name
            ),
            updated_at = now()
            WHERE package_detail IS NOT NULL
              AND btrim(package_detail) <> ''
            """
        )
    )
    op.drop_column("mdm_packages", "package_detail")


def downgrade() -> None:
    op.add_column("mdm_packages", sa.Column("package_detail", sa.Text(), nullable=True))
