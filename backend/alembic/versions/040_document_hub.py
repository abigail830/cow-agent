"""Document Hub tables, session imports, parse_job_runs scope."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "040"
down_revision: Union[str, Sequence[str], None] = "039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hub_folders",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hub_folders.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_hub_folders_user_id", "hub_folders", ["user_id"])
    op.create_index("uq_hub_folders_user_parent_name", "hub_folders", ["user_id", "parent_id", "name"], unique=True)

    op.create_table(
        "hub_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("folder_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hub_folders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_kind", sa.String(length=32), server_default="file", nullable=False),
        sa.Column("filename", sa.String(length=500), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=50), server_default="inline", nullable=False),
        sa.Column("provider_file_id", sa.String(length=255), nullable=False),
        sa.Column("gist", sa.Text(), nullable=True),
        sa.Column("gist_content_sha256", sa.String(length=64), nullable=True),
        sa.Column("gist_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parse_status", sa.String(length=32), server_default="ready", nullable=False),
        sa.Column("parse_pipeline_id", sa.String(length=64), nullable=True),
        sa.Column("parse_job_id", sa.String(length=64), nullable=True),
        sa.Column("parse_error_code", sa.String(length=64), nullable=True),
        sa.Column("parse_error_message", sa.Text(), nullable=True),
        sa.Column("parse_stage_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("parsed_artifact_manifest", postgresql.JSONB(), nullable=True),
        sa.Column("capture_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("attachment_role", sa.String(length=32), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_hub_items_user_id", "hub_items", ["user_id"])
    op.create_index("idx_hub_items_folder_id", "hub_items", ["folder_id"])
    op.create_index("idx_hub_items_content_hash", "hub_items", ["user_id", "content_hash"])

    op.create_table(
        "hub_audio_captures",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("folder_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hub_folders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("host_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("hub_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parse_job_id", sa.String(length=64), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("context_snapshot", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_hub_audio_captures_user_id", "hub_audio_captures", ["user_id"])

    op.create_foreign_key(
        "fk_hub_items_capture_id",
        "hub_items",
        "hub_audio_captures",
        ["capture_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "chat_document_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("chat_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("chats.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("ref_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "imported_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_mentioned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_chat_document_imports_chat_id", "chat_document_imports", ["chat_id"])
    op.create_index(
        "uq_chat_document_imports_chat_source_ref",
        "chat_document_imports",
        ["chat_id", "source", "ref_id"],
        unique=True,
    )

    op.add_column(
        "parse_job_runs",
        sa.Column("document_scope", sa.String(length=16), server_default="chat", nullable=False),
    )
    op.alter_column("parse_job_runs", "chat_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)


def downgrade() -> None:
    op.alter_column("parse_job_runs", "chat_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.drop_column("parse_job_runs", "document_scope")
    op.drop_table("chat_document_imports")
    op.drop_constraint("fk_hub_items_capture_id", "hub_items", type_="foreignkey")
    op.drop_table("hub_audio_captures")
    op.drop_table("hub_items")
    op.drop_table("hub_folders")
