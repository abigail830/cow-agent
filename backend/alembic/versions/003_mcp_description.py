"""mcp_servers description column

Revision ID: 003
Revises: 002
Create Date: 2026-06-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, Sequence[str], None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("mcp_servers", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("mcp_servers", "description")
