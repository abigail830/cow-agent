"""Add content_hash to chat_attachments for upload deduplication."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "026"
down_revision: Union[str, Sequence[str], None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_attachments", sa.Column("content_hash", sa.String(64), nullable=True))
    op.create_index(
        "idx_chat_attachments_chat_content_hash",
        "chat_attachments",
        ["chat_id", "content_hash"],
    )


def downgrade() -> None:
    op.drop_index("idx_chat_attachments_chat_content_hash", table_name="chat_attachments")
    op.drop_column("chat_attachments", "content_hash")
