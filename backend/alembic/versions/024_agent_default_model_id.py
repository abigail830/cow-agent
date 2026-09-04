"""agents.default_model_id for profile catalog defaults

Revision ID: 024
Revises: 023
Create Date: 2026-09-04
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "024"
down_revision: Union[str, Sequence[str], None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("default_model_id", sa.String(64), nullable=True))


def downgrade() -> None:
    op.drop_column("agents", "default_model_id")
