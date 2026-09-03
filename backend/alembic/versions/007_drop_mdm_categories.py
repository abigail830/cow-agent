"""drop mdm_categories — category routing lives in knowledge/categories.yaml

Revision ID: 007
Revises: 006
Create Date: 2026-06-16
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "007"
down_revision: Union[str, Sequence[str], None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("mdm_services_category_id_fkey", "mdm_services", type_="foreignkey")
    op.drop_constraint("mdm_packages_category_id_fkey", "mdm_packages", type_="foreignkey")
    op.drop_table("mdm_categories")


def downgrade() -> None:
    op.create_table(
        "mdm_categories",
        sa.Column("category_id", sa.String(64), primary_key=True),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("region", sa.String(16), nullable=False),
        sa.Column("bu", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("default_currency", sa.String(8), nullable=True),
        sa.Column(
            "available_templates",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "pricing_types",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "line_grouping",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "capabilities",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "pricing_facts_schema",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "selection_rules",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "ai_hints",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("knowledge_graph_ref", sa.String(64), nullable=True),
        sa.Column("source_file", sa.String(255), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_foreign_key(
        "mdm_services_category_id_fkey",
        "mdm_services",
        "mdm_categories",
        ["category_id"],
        ["category_id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "mdm_packages_category_id_fkey",
        "mdm_packages",
        "mdm_categories",
        ["category_id"],
        ["category_id"],
        ondelete="CASCADE",
    )
