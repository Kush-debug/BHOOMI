"""Phase 6: evidence sufficiency scores and investigation cases.

Revision ID: 0005_phase6_sufficiency_investigation
Revises: 0004_phase5_events_findings
Create Date: 2026-09-04

BHUMI_FORENSICS_SPEC.md §3.3 / §5.7 / §5.9 / §9. Purely additive:

  - new table: evidence_sufficiency_scores (persisted score breakdowns)
  - new table: investigation_cases

`Finding.evidence_sufficiency` already exists as a column (added, NULL, in
0004) — Phase 6 only starts writing to it; no schema change needed there.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.database.base import Base
import app.models  # noqa: F401  (registers EvidenceSufficiencyScore/InvestigationCase on Base.metadata)

revision: str = "0005_phase6_sufficiency_investigation"
down_revision: Union[str, None] = "0004_phase5_events_findings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    # checkfirst=True: creates only the tables that don't already exist,
    # same pattern 0003/0004 use, safe whether or not this is a fresh install.
    Base.metadata.create_all(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())
    for table in ("investigation_cases", "evidence_sufficiency_scores"):
        if table in existing_tables:
            op.drop_table(table)
