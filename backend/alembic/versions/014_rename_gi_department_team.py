"""rename GI department_team to Global Incentive

Revision ID: 014
Revises: 013
Create Date: 2026-06-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, Sequence[str], None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE mdm_services
            SET department_team = 'Global Incentive',
                updated_at = now()
            WHERE region = 'AU'
              AND (
                department_team = 'R&D Tax Incentive Services'
                OR upper(sku) LIKE 'GI%'
              )
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE mdm_services
            SET department_team = 'R&D Tax Incentive Services',
                updated_at = now()
            WHERE region = 'AU'
              AND (
                department_team = 'Global Incentive'
                OR upper(sku) LIKE 'GI%'
              )
            """
        )
    )
