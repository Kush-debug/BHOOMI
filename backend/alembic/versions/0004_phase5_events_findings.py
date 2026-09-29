"""Phase 5: land events + findings.

Revision ID: 0004_phase5_events_findings
Revises: 0003_phase3_parcel_identity
Create Date: 2026-09-04

BHUMI_FORENSICS_SPEC.md §3.3 / §5.5 / §5.6. Purely additive: two new tables
(land_events, findings). Phase 4 (timeline reconstruction) added no tables —
snapshots and transitions are computed live — so this is the first migration
since Phase 3.

Nothing is backfilled. Events and findings are (re)generated whenever a
parcel's documents are processed; existing parcels get them on the next
reprocess. Downgrade drops both tables cleanly — nothing else depends on
them yet.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.database.base import Base
import app.models  # noqa: F401  (registers LandEvent / Finding on Base.metadata)

revision: str = "0004_phase5_events_findings"
down_revision: Union[str, None] = "0003_phase3_parcel_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # Create land_events / findings if they don't exist yet. checkfirst keeps
    # this safe on a database that already has some of Base's tables.
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for table in ("findings", "land_events"):
        if table in existing:
            op.drop_table(table)
