"""UI projection via chat_events; drop legacy messages table."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "030"
down_revision: Union[str, Sequence[str], None] = "029"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chat_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False, server_default="message"),
        sa.Column("payload", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("chat_id", "sequence", name="uq_chat_events_chat_sequence"),
    )
    op.create_index("idx_chat_events_chat_id", "chat_events", ["chat_id", "sequence"])

    op.drop_constraint("chat_attachments_message_id_fkey", "chat_attachments", type_="foreignkey")
    op.drop_table("messages")


def downgrade() -> None:
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chat_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("message_type", sa.String(length=30), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}"),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_messages_chat_id", "messages", ["chat_id", "sequence"])
    op.create_index("idx_messages_type", "messages", ["message_type"])

    op.create_foreign_key(
        "chat_attachments_message_id_fkey",
        "chat_attachments",
        "messages",
        ["message_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_index("idx_chat_events_chat_id", table_name="chat_events")
    op.drop_table("chat_events")
