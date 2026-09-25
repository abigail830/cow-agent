"""Audio capture tables and attachment capture linkage."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "038"
down_revision: Union[str, Sequence[str], None] = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audio_captures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "chat_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "host_attachment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_attachments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "input_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "output_annotation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("chat_ui_annotations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("parse_job_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column(
            "context_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("idx_audio_captures_chat_id", "audio_captures", ["chat_id"])

    op.add_column(
        "chat_attachments",
        sa.Column("capture_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "chat_attachments",
        sa.Column("attachment_role", sa.String(length=32), nullable=True),
    )
    op.create_foreign_key(
        "fk_chat_attachments_capture_id",
        "chat_attachments",
        "audio_captures",
        ["capture_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_chat_attachments_capture_id", "chat_attachments", type_="foreignkey")
    op.drop_column("chat_attachments", "attachment_role")
    op.drop_column("chat_attachments", "capture_id")
    op.drop_index("idx_audio_captures_chat_id", table_name="audio_captures")
    op.drop_table("audio_captures")
