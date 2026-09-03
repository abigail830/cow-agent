"""mdm catalog tables (simulated MDM product master)

Revision ID: 006
Revises: 005
Create Date: 2026-06-16

Tables prefixed mdm_* simulate upstream MDM until an API is available.
proposal-composer (and MCP postgres read tools) query these tables directly.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "006"
down_revision: Union[str, Sequence[str], None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mdm_categories",
        sa.Column("category_id", sa.String(64), primary_key=True),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("region", sa.String(16), nullable=False),
        sa.Column("bu", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("default_currency", sa.String(8)),
        sa.Column("available_templates", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("pricing_types", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("line_grouping", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("capabilities", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("pricing_facts_schema", postgresql.JSONB(), server_default="[]", nullable=False),
        sa.Column("selection_rules", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("ai_hints", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("knowledge_graph_ref", sa.String(64)),
        sa.Column("source_file", sa.String(255)),
        sa.Column("status", sa.String(16), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "mdm_services",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("sku", sa.String(128), nullable=False),
        sa.Column(
            "category_id",
            sa.String(64),
            sa.ForeignKey("mdm_categories.category_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("region", sa.String(16), nullable=False),
        sa.Column("bu", sa.String(64), nullable=False),
        sa.Column("department_team", sa.String(64)),
        sa.Column("service_group", sa.String(64)),
        sa.Column("service_group_display", sa.String(128)),
        sa.Column("product_name", sa.Text(), nullable=False),
        sa.Column("service_name_on_proposal", sa.Text(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("scope_of_work", sa.Text()),
        sa.Column("service_type", sa.String(32), nullable=False),
        sa.Column("billing_frequency", sa.String(16), nullable=False),
        sa.Column("recurring", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), server_default="ACTIVE", nullable=False),
        sa.Column("pricing_type", sa.String(32), nullable=False),
        sa.Column("price_currency", sa.String(8), nullable=False),
        sa.Column("price_amount", sa.Numeric(18, 2)),
        sa.Column("price_min", sa.Numeric(18, 2)),
        sa.Column("price_max", sa.Numeric(18, 2)),
        sa.Column("price_spec", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("fee_raw", sa.Text()),
        sa.Column("footnotes", sa.Text()),
        sa.Column("sku_semantic_for_ai", sa.Text()),
        sa.Column("external_record_id", sa.String(64)),
        sa.Column("source_sheet", sa.String(64)),
        sa.Column("source_row", sa.Integer()),
        sa.Column("extensions", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("sku", "category_id", name="uq_mdm_services_sku_category"),
    )
    op.create_index("idx_mdm_services_category", "mdm_services", ["category_id"])
    op.create_index("idx_mdm_services_group", "mdm_services", ["category_id", "service_group"])
    op.create_index("idx_mdm_services_status", "mdm_services", ["status"])

    op.create_table(
        "mdm_packages",
        sa.Column("package_id", sa.String(64), primary_key=True),
        sa.Column(
            "category_id",
            sa.String(64),
            sa.ForeignKey("mdm_categories.category_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("region", sa.String(16), nullable=False),
        sa.Column("bu", sa.String(64), nullable=False),
        sa.Column("package_name", sa.String(255), nullable=False),
        sa.Column("package_detail", sa.Text()),
        sa.Column("package_semantic_for_ai", sa.Text()),
        sa.Column("status", sa.String(16), server_default="ACTIVE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("idx_mdm_packages_category", "mdm_packages", ["category_id"])

    op.create_table(
        "mdm_package_services",
        sa.Column(
            "package_id",
            sa.String(64),
            sa.ForeignKey("mdm_packages.package_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("category_id", sa.String(64), primary_key=True),
        sa.Column("sku", sa.String(128), primary_key=True),
        sa.Column(
            "service_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mdm_services.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    op.create_table(
        "mdm_package_name_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("region", sa.String(16), server_default="AU", nullable=False),
        sa.Column("legacy_name", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("mdm_package_name_aliases")
    op.drop_table("mdm_package_services")
    op.drop_index("idx_mdm_packages_category", table_name="mdm_packages")
    op.drop_table("mdm_packages")
    op.drop_index("idx_mdm_services_status", table_name="mdm_services")
    op.drop_index("idx_mdm_services_group", table_name="mdm_services")
    op.drop_index("idx_mdm_services_category", table_name="mdm_services")
    op.drop_table("mdm_services")
    op.drop_table("mdm_categories")
