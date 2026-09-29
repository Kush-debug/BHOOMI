"""Phase 3: parcel identity — parcels, persons, and claim linkage.

Revision ID: 0003_phase3_parcel_identity
Revises: 0002_phase2_evidence_foundation
Create Date: 2026-09-04

BHUMI_FORENSICS_SPEC.md §3.2 / §9. Purely additive:

  - new tables: parcels, parcel_identifier_aliases, persons, person_aliases
  - new nullable columns on claims: parcel_id, person_id

Nothing is migrated or backfilled — existing claims simply have NULL
parcel_id/person_id until the next time their document is processed, at
which point IdentityResolver resolves them. That's an honest state (not yet
resolved), not a data-loss risk.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.database.base import Base
import app.models  # noqa: F401  (registers Parcel/Person/etc. on Base.metadata)

revision: str = "0003_phase3_parcel_identity"
down_revision: Union[str, None] = "0002_phase2_evidence_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Create parcels / parcel_identifier_aliases / persons / person_aliases
    #    if they don't exist yet (fresh installs get them from 0001 already).
    Base.metadata.create_all(bind=bind, checkfirst=True)
    existing_tables = set(sa.inspect(bind).get_table_names())

    # 2. Add parcel_id / person_id to claims wherever they're missing.
    if "claims" in existing_tables:
        present = {c["name"] for c in sa.inspect(bind).get_columns("claims")}
        if "parcel_id" not in present:
            op.add_column("claims", sa.Column("parcel_id", sa.Integer(), nullable=True))
            op.create_index("ix_claims_parcel_id", "claims", ["parcel_id"])
        if "person_id" not in present:
            op.add_column("claims", sa.Column("person_id", sa.Integer(), nullable=True))
            op.create_index("ix_claims_person_id", "claims", ["person_id"])


def downgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())
    if "claims" in existing_tables:
        present = {c["name"] for c in sa.inspect(bind).get_columns("claims")}
        if "person_id" in present:
            op.drop_column("claims", "person_id")
        if "parcel_id" in present:
            op.drop_column("claims", "parcel_id")
    for table in ("person_aliases", "persons", "parcel_identifier_aliases", "parcels"):
        if table in existing_tables:
            op.drop_table(table)
