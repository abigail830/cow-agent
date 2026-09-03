"""rename AU MDM scope to au-advisory / Incorp

Revision ID: 012
Revises: 011
Create Date: 2026-06-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, Sequence[str], None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE mdm_services
            SET category_id = 'au-advisory',
                bu = 'Incorp',
                updated_at = now()
            WHERE category_id = 'au-services'
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE mdm_packages
            SET category_id = 'au-advisory',
                bu = 'Incorp',
                updated_at = now()
            WHERE category_id = 'au-services'
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE mdm_package_services
            SET category_id = 'au-advisory'
            WHERE category_id = 'au-services'
            """
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            UPDATE mdm_package_services
            SET category_id = 'au-services'
            WHERE category_id = 'au-advisory'
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE mdm_packages
            SET category_id = 'au-services',
                bu = 'Tax and Advisory',
                updated_at = now()
            WHERE category_id = 'au-advisory'
            """
        )
    )
    connection.execute(
        sa.text(
            """
            UPDATE mdm_services
            SET category_id = 'au-services',
                bu = 'Tax and Advisory',
                updated_at = now()
            WHERE category_id = 'au-advisory'
            """
        )
    )
