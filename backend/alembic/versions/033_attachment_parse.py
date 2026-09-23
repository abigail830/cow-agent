"""Add parse status columns and parse job mirror tables for attachment ingest."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "033"
down_revision: Union[str, Sequence[str], None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_attachments",
        sa.Column("parse_status", sa.String(length=32), nullable=False, server_default="ready"),
    )
    op.add_column(
        "chat_attachments",
        sa.Column("parse_pipeline_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "chat_attachments",
        sa.Column("parse_job_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "chat_attachments",
        sa.Column("parse_error_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "chat_attachments",
        sa.Column("parse_error_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "chat_attachments",
        sa.Column("parse_stage_snapshot", JSONB(), nullable=True),
    )
    op.create_index("idx_chat_attachments_parse_job_id", "chat_attachments", ["parse_job_id"])

    op.create_table(
        "parse_job_events",
        sa.Column("event_id", sa.String(length=128), primary_key=True),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("attachment_id", UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload_json", JSONB(), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("idx_parse_job_events_job_id", "parse_job_events", ["job_id"])

    op.create_table(
        "parse_job_runs",
        sa.Column("job_id", sa.String(length=64), primary_key=True),
        sa.Column("attachment_id", UUID(as_uuid=True), nullable=False),
        sa.Column("chat_id", UUID(as_uuid=True), nullable=False),
        sa.Column("run_token_hash", sa.String(length=64), nullable=False),
        sa.Column("webhook_secret", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("job_payload_json", JSONB(), nullable=False),
        sa.Column("github_run_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("idx_parse_job_runs_attachment_id", "parse_job_runs", ["attachment_id"])


def downgrade() -> None:
    op.drop_index("idx_parse_job_runs_attachment_id", table_name="parse_job_runs")
    op.drop_table("parse_job_runs")
    op.drop_index("idx_parse_job_events_job_id", table_name="parse_job_events")
    op.drop_table("parse_job_events")
    op.drop_index("idx_chat_attachments_parse_job_id", table_name="chat_attachments")
    op.drop_column("chat_attachments", "parse_stage_snapshot")
    op.drop_column("chat_attachments", "parse_error_message")
    op.drop_column("chat_attachments", "parse_error_code")
    op.drop_column("chat_attachments", "parse_job_id")
    op.drop_column("chat_attachments", "parse_pipeline_id")
    op.drop_column("chat_attachments", "parse_status")
