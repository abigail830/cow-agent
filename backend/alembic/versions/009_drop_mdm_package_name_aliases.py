"""apply package name aliases, merge duplicates, drop alias table

Revision ID: 009
Revises: 008
Create Date: 2026-06-19
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, Sequence[str], None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _split_canonical_package(canonical_name: str) -> tuple[str, str | None, str]:
    if "*" in canonical_name:
        name, detail = canonical_name.split("*", 1)
        name = name.strip()
        detail = detail.strip() or None
    else:
        name = canonical_name.strip()
        detail = None
    semantic = f"{name}*{detail}" if detail else name
    return name, detail, semantic


def upgrade() -> None:
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    if "mdm_package_name_aliases" not in inspector.get_table_names():
        return

    rows = connection.execute(
        sa.text("SELECT legacy_name, canonical_name FROM mdm_package_name_aliases")
    ).fetchall()

    find_legacy = sa.text(
        """
        SELECT package_id, category_id
        FROM mdm_packages
        WHERE package_name = :legacy
           OR (package_detail IS NOT NULL AND package_name || ' - ' || package_detail = :legacy)
        """
    )
    find_canonical = sa.text(
        """
        SELECT package_id
        FROM mdm_packages
        WHERE category_id = :category_id
          AND package_name = :name
          AND COALESCE(package_detail, '') = COALESCE(:detail, '')
          AND package_id <> :exclude_id
        LIMIT 1
        """
    )
    move_links = sa.text(
        """
        INSERT INTO mdm_package_services (package_id, category_id, sku, service_id)
        SELECT :target_id, category_id, sku, service_id
        FROM mdm_package_services
        WHERE package_id = :source_id
        ON CONFLICT (package_id, category_id, sku) DO NOTHING
        """
    )
    delete_links = sa.text("DELETE FROM mdm_package_services WHERE package_id = :package_id")
    delete_package = sa.text("DELETE FROM mdm_packages WHERE package_id = :package_id")
    update_package = sa.text(
        """
        UPDATE mdm_packages
        SET package_name = :name,
            package_detail = :detail,
            package_semantic_for_ai = :semantic,
            updated_at = now()
        WHERE package_id = :package_id
        """
    )

    for legacy_name, canonical_name in rows:
        legacy = str(legacy_name).strip()
        name, detail, semantic = _split_canonical_package(str(canonical_name))
        legacy_rows = connection.execute(find_legacy, {"legacy": legacy}).fetchall()
        for package_id, category_id in legacy_rows:
            duplicate = connection.execute(
                find_canonical,
                {
                    "category_id": category_id,
                    "name": name,
                    "detail": detail,
                    "exclude_id": package_id,
                },
            ).scalar()
            if duplicate:
                connection.execute(move_links, {"target_id": duplicate, "source_id": package_id})
                connection.execute(delete_links, {"package_id": package_id})
                connection.execute(delete_package, {"package_id": package_id})
            else:
                connection.execute(
                    update_package,
                    {
                        "package_id": package_id,
                        "name": name,
                        "detail": detail,
                        "semantic": semantic,
                    },
                )

    connection.execute(
        sa.text(
            """
            UPDATE mdm_packages
            SET package_semantic_for_ai = CASE
                WHEN package_detail IS NOT NULL AND package_detail <> ''
                    THEN package_name || '*' || package_detail
                ELSE package_name
            END,
            updated_at = now()
            WHERE region = 'AU'
            """
        )
    )

    op.drop_table("mdm_package_name_aliases")


def downgrade() -> None:
    from sqlalchemy.dialects import postgresql

    op.create_table(
        "mdm_package_name_aliases",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("region", sa.String(16), server_default="AU", nullable=False),
        sa.Column("legacy_name", sa.Text(), nullable=False),
        sa.Column("canonical_name", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
