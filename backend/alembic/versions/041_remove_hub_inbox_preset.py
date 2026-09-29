"""Remove legacy auto-created Document Hub «Inbox» root folders."""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "041"
down_revision: Union[str, Sequence[str], None] = "040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Child hub_folders / hub_items / hub_audio_captures cascade via FK on delete.
    op.execute(
        """
        DELETE FROM hub_folders
        WHERE name = 'Inbox'
          AND parent_id IS NULL
        """
    )


def downgrade() -> None:
    pass
