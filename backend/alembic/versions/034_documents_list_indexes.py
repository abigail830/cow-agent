"""Indexes to speed up cross-session document list queries."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "034"
down_revision: Union[str, Sequence[str], None] = "033"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("idx_chats_user_id", "chats", ["user_id"])
    op.create_index(
        "idx_chat_attachments_created_at",
        "chat_attachments",
        ["created_at"],
        postgresql_ops={"created_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("idx_chat_attachments_created_at", table_name="chat_attachments")
    op.drop_index("idx_chats_user_id", table_name="chats")
