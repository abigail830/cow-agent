"""Persist per-user per-agent chat model selection in Postgres."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "028"
down_revision: Union[str, Sequence[str], None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_agent_model_preferences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.UUID(), nullable=False),
        sa.Column("model_id", sa.String(64), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "agent_id", name="uq_user_agent_model_preferences"),
    )
    op.create_index(
        "idx_user_agent_model_preferences_user_agent",
        "user_agent_model_preferences",
        ["user_id", "agent_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_user_agent_model_preferences_user_agent", table_name="user_agent_model_preferences")
    op.drop_table("user_agent_model_preferences")
