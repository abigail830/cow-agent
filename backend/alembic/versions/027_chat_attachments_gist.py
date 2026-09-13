"""Add gist to chat_attachments for attachment catalog index."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: Union[str, Sequence[str], None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_attachments", sa.Column("gist", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_attachments", "gist")
