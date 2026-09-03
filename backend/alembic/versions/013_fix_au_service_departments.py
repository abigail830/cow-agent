"""fix AU service department_team and reaffirm au-advisory / Incorp

Revision ID: 013
Revises: 012
Create Date: 2026-06-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, Sequence[str], None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE mdm_services
            SET category_id = 'au-advisory',
                bu = 'Incorp',
                department_team = CASE
                    WHEN upper(sku) LIKE 'SMSF%' THEN 'SMSF'
                    WHEN upper(sku) LIKE 'CSS NEW ITEM%'
                      OR upper(sku) LIKE 'CSS%' THEN 'Corporate Secretarial Services'
                    WHEN upper(sku) LIKE 'FF NEW ITEM%'
                      OR upper(sku) LIKE 'FF%' THEN 'Finance Function'
                    WHEN upper(sku) LIKE 'TA NEW ITEM%'
                      OR upper(sku) LIKE 'TA%' THEN 'Tax and Advisory'
                    WHEN upper(sku) LIKE 'GI%' THEN 'R&D Tax Incentive Services'
                    WHEN upper(sku) LIKE 'SP%' THEN 'Specialist Projects'
                    ELSE department_team
                END,
                updated_at = now()
            WHERE region = 'AU'
            """
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE mdm_services
            SET department_team = CASE
                    WHEN upper(sku) LIKE 'SMSF%' THEN 'SM'
                    WHEN upper(sku) LIKE 'CSS%' THEN 'CS'
                    WHEN upper(sku) LIKE 'FF%' THEN 'FF'
                    WHEN upper(sku) LIKE 'TA%' THEN 'TA'
                    WHEN upper(sku) LIKE 'GI%' THEN 'GI'
                    WHEN upper(sku) LIKE 'SP%' THEN 'SP'
                    ELSE department_team
                END,
                updated_at = now()
            WHERE region = 'AU'
            """
        )
    )
