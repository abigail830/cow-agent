"""Alembic env for optional JOB_STORE=postgres (profile B).

Run: alembic -c alembic.ini upgrade head
Uses DATABASE_URL from parse-pipeline .env when implemented.
"""

from __future__ import annotations

raise NotImplementedError(
    "Postgres job store migrations are not implemented yet. Use JOB_STORE=memory."
)
