"""seed harneys-bvi MDM catalog from bundled snapshot

Revision ID: 008
Revises: 007
Create Date: 2026-06-19
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "008"
down_revision: Union[str, Sequence[str], None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.mdm.seed import seed_bvi_catalog_sync
    from app.mdm.snapshot_io import load_bvi_catalog_json

    snapshot = load_bvi_catalog_json()
    counts = seed_bvi_catalog_sync(op.get_bind(), snapshot)
    print(f"Seeded BVI MDM catalog: {counts}")


def downgrade() -> None:
    from sqlalchemy import delete
    from sqlalchemy.orm import Session

    from app.db.mdm_models import MdmPackage, MdmPackageService, MdmService
    from app.mdm.excel_import import BVI_CATEGORY_ID

    session = Session(bind=op.get_bind())
    try:
        session.execute(delete(MdmPackageService).where(MdmPackageService.category_id == BVI_CATEGORY_ID))
        session.execute(delete(MdmPackage).where(MdmPackage.category_id == BVI_CATEGORY_ID))
        session.execute(delete(MdmService).where(MdmService.category_id == BVI_CATEGORY_ID))
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
