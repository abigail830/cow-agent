"""Add gist_content_sha256 and gist_generated_at to chat_attachments."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "039"
down_revision: Union[str, Sequence[str], None] = "038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_attachments",
        sa.Column("gist_content_sha256", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "chat_attachments",
        sa.Column("gist_generated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_attachments", "gist_generated_at")
    op.drop_column("chat_attachments", "gist_content_sha256")
