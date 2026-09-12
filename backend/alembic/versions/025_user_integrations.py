"""user oauth integrations for remote MCP servers

Revision ID: 025
Revises: 024
Create Date: 2026-09-12
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "025"
down_revision: Union[str, Sequence[str], None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="disconnected"),
        sa.Column("account_label", sa.String(255), nullable=True),
        sa.Column("secrets_encrypted", sa.Text(), nullable=False, server_default=""),
        sa.Column("integration_metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("connection_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_user_integrations_user_id", "user_integrations", ["user_id"])
    op.create_index(
        "uq_user_integrations_user_provider",
        "user_integrations",
        ["user_id", "provider"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_user_integrations_user_provider", table_name="user_integrations")
    op.drop_index("idx_user_integrations_user_id", table_name="user_integrations")
    op.drop_table("user_integrations")
