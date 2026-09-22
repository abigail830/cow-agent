"""Unified MAF transcript: chat_messages, chat_ui_annotations, chat_runs; drop chat_events."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "031"
down_revision: Union[str, Sequence[str], None] = "030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chats",
        sa.Column("transcript_seq", sa.Integer(), nullable=False, server_default="1"),
    )

    op.create_table(
        "chat_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chat_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("model_id", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_chat_runs_chat_id", "chat_runs", ["chat_id", "started_at"])

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chat_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("turn_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("maf_message_id", sa.String(length=128), nullable=True),
        sa.Column("body", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("chat_id", "sequence", name="uq_chat_messages_chat_sequence"),
        sa.UniqueConstraint("chat_id", "maf_message_id", name="uq_chat_messages_chat_maf_message_id"),
    )
    op.create_index("idx_chat_messages_chat_sequence", "chat_messages", ["chat_id", "sequence"])
    op.create_index("idx_chat_messages_chat_turn", "chat_messages", ["chat_id", "turn_id"])

    op.create_foreign_key(
        "chat_runs_user_message_id_fkey",
        "chat_runs",
        "chat_messages",
        ["user_message_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "chat_messages_run_id_fkey",
        "chat_messages",
        "chat_runs",
        ["run_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "chat_ui_annotations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "chat_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("turn_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("anchor_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("ref", sa.String(length=255), nullable=False),
        sa.Column("display", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("chat_id", "sequence", name="uq_chat_ui_annotations_chat_sequence"),
    )
    op.create_index("idx_chat_ui_annotations_chat_sequence", "chat_ui_annotations", ["chat_id", "sequence"])
    op.create_foreign_key(
        "chat_ui_annotations_anchor_message_id_fkey",
        "chat_ui_annotations",
        "chat_messages",
        ["anchor_message_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 030 dropped `messages` but left orphan message_id values on attachments.
    # chat_messages starts empty (no chat_events backfill), so clear stale refs.
    op.execute(
        sa.text(
            "UPDATE chat_attachments SET message_id = NULL "
            "WHERE message_id IS NOT NULL "
            "AND message_id NOT IN (SELECT id FROM chat_messages)"
        )
    )
    op.create_foreign_key(
        "chat_attachments_message_id_fkey",
        "chat_attachments",
        "chat_messages",
        ["message_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.drop_index("idx_chat_events_chat_id", table_name="chat_events")
    op.drop_table("chat_events")


def downgrade() -> None:
    op.drop_constraint("chat_attachments_message_id_fkey", "chat_attachments", type_="foreignkey")

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

    op.drop_index("idx_chat_ui_annotations_chat_sequence", table_name="chat_ui_annotations")
    op.drop_table("chat_ui_annotations")

    op.drop_constraint("chat_messages_run_id_fkey", "chat_messages", type_="foreignkey")
    op.drop_constraint("chat_runs_user_message_id_fkey", "chat_runs", type_="foreignkey")
    op.drop_index("idx_chat_messages_chat_turn", table_name="chat_messages")
    op.drop_index("idx_chat_messages_chat_sequence", table_name="chat_messages")
    op.drop_table("chat_messages")

    op.drop_index("idx_chat_runs_chat_id", table_name="chat_runs")
    op.drop_table("chat_runs")

    op.drop_column("chats", "transcript_seq")
