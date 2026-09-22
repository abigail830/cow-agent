"""Wipe all chat sessions and transcript data for unified-transcript fresh start.

Revision ID: 032
Revises: 031
Create Date: 2026-09-22

One-time data migration: removes orphan chat shells left after 031 (chats rows
without chat_messages). Irreversible — downgrade is a no-op.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "032"
down_revision: Union[str, Sequence[str], None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "TRUNCATE TABLE chat_attachments, chat_ui_annotations, "
            "chat_messages, chat_runs, chats RESTART IDENTITY CASCADE"
        )
    )


def downgrade() -> None:
    # Data wipe cannot be restored.
    pass
