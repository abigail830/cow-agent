"""Partial indexes for cross-session artifact document lists."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "037"
down_revision: Union[str, Sequence[str], None] = "036"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_cua_artifact_dedup",
        "chat_ui_annotations",
        ["chat_id", "ref", "sequence"],
        postgresql_where=sa.text("kind = 'artifact'"),
        postgresql_ops={"sequence": "DESC"},
    )
    op.create_index(
        "idx_cua_artifact_created_at",
        "chat_ui_annotations",
        ["created_at"],
        postgresql_where=sa.text("kind = 'artifact'"),
        postgresql_ops={"created_at": "DESC"},
    )


def downgrade() -> None:
    op.drop_index("idx_cua_artifact_created_at", table_name="chat_ui_annotations")
    op.drop_index("idx_cua_artifact_dedup", table_name="chat_ui_annotations")
