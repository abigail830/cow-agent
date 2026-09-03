"""store AU canonical package label in package_name (Name*Detail)

Revision ID: 010
Revises: 009
Create Date: 2026-06-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, Sequence[str], None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE mdm_packages
            SET package_name = package_name || '*' || package_detail,
                package_semantic_for_ai = package_name || '*' || package_detail,
                package_detail = NULL,
                updated_at = now()
            WHERE region = 'AU'
              AND package_detail IS NOT NULL
              AND btrim(package_detail) <> ''
              AND package_name NOT LIKE '%*%'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE mdm_packages
            SET package_name = split_part(package_name, '*', 1),
                package_detail = NULLIF(split_part(package_name, '*', 2), ''),
                package_semantic_for_ai = package_name,
                updated_at = now()
            WHERE region = 'AU'
              AND package_name LIKE '%*%'
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE mdm_packages
            SET package_semantic_for_ai = COALESCE(package_detail, package_name),
                updated_at = now()
            WHERE region = 'AU'
              AND package_detail IS NOT NULL
            """
        )
    )
