"""Phase 1 baseline: full schema plus provenance and honesty columns.

Revision ID: 0001_phase1_baseline
Revises:
Create Date: 2026-09-03

This baseline is written to be safe on two starting points:

  a) a fresh database  -> every table is created from the current models
  b) an existing database created by the old `Base.metadata.create_all()`
     -> tables already exist, so only the columns Phase 1 adds are applied

It therefore introspects before it writes. From Phase 2 onward, migrations are
generated normally with `alembic revision --autogenerate`.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.database.base import Base
import app.models  # noqa: F401  (registers every model on Base.metadata)

revision: str = "0001_phase1_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Columns Phase 1 introduces, applied only where they are missing.
NEW_COLUMNS = {
    "documents": [
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.Column("page_count", sa.Integer(), nullable=True),
        sa.Column("source_class", sa.String(20), nullable=True),
        sa.Column("processing_error_code", sa.String(64), nullable=True),
        sa.Column("processing_error_message", sa.Text(), nullable=True),
        sa.Column("processing_failed_stage", sa.String(32), nullable=True),
    ],
    "ocr_results": [
        sa.Column("engine_version", sa.String(50), nullable=True),
        sa.Column("engine_languages", sa.String(100), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=True),
        sa.Column("page_width", sa.Integer(), nullable=True),
        sa.Column("page_height", sa.Integer(), nullable=True),
    ],
    "extracted_fields": [
        sa.Column("confidence_basis", sa.String(200), nullable=True),
        sa.Column("bbox_source", sa.String(20), nullable=True),
        sa.Column("provenance", sa.String(24), nullable=True),
    ],
    "gis_parcels": [
        sa.Column("source_class", sa.String(32), nullable=True),
    ],
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # 1. Create any table that does not exist yet.
    Base.metadata.create_all(bind=bind, checkfirst=True)

    existing_tables = set(inspector.get_table_names())

    # 2. Add the Phase 1 columns wherever they are missing.
    for table, columns in NEW_COLUMNS.items():
        if table not in existing_tables:
            continue  # freshly created above, already has them
        present = {c["name"] for c in sa.inspect(bind).get_columns(table)}
        for column in columns:
            if column.name not in present:
                op.add_column(table, column.copy())

    # 3. Backfill provenance so no row is left with an ambiguous NULL.
    if "documents" in existing_tables:
        op.execute(
            sa.text("UPDATE documents SET source_class = 'REAL_UPLOAD' WHERE source_class IS NULL")
        )
    if "extracted_fields" in existing_tables:
        op.execute(
            sa.text(
                "UPDATE extracted_fields SET provenance = 'DOCUMENT_OCR' WHERE provenance IS NULL"
            )
        )
        # Historic rows carry placeholder boxes that did not come from OCR. They
        # are marked NONE so the UI stops presenting them as source regions.
        op.execute(
            sa.text("UPDATE extracted_fields SET bbox_source = 'NONE' WHERE bbox_source IS NULL")
        )
    if "gis_parcels" in existing_tables:
        op.execute(
            sa.text(
                "UPDATE gis_parcels SET source_class = 'SEED_SYNTHETIC' WHERE source_class IS NULL"
            )
        )

    # 4. Index for duplicate-upload detection.
    try:
        op.create_index("ix_documents_sha256", "documents", ["sha256"])
    except Exception:
        pass  # already present


def downgrade() -> None:
    for table, columns in NEW_COLUMNS.items():
        for column in columns:
            try:
                op.drop_column(table, column.name)
            except Exception:
                pass
