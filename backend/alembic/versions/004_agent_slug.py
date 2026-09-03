"""agents slug column

Revision ID: 004
Revises: 003
Create Date: 2026-06-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, Sequence[str], None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("slug", sa.String(64), nullable=True))
    op.create_index("ix_agents_slug", "agents", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_agents_slug", table_name="agents")
    op.drop_column("agents", "slug")
