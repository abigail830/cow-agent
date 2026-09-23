"""Store parsed artifact manifest on chat_attachments."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "035"
down_revision: Union[str, Sequence[str], None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("chat_attachments", sa.Column("parsed_artifact_manifest", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("chat_attachments", "parsed_artifact_manifest")
