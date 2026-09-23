"""Wipe chat attachment rows and parse job mirror tables.

Revision ID: 036
Revises: 035
Create Date: 2026-09-23

One-time data migration before manifest-only parsed artifact reads.
Irreversible — downgrade is a no-op.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "036"
down_revision: Union[str, Sequence[str], None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "TRUNCATE TABLE parse_job_events, parse_job_runs, chat_attachments RESTART IDENTITY CASCADE"
        )
    )


def downgrade() -> None:
    pass
