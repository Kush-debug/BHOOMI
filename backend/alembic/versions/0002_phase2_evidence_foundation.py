"""Phase 2: evidence foundation — ocr_runs, evidence_regions, claims.

Revision ID: 0002_phase2_evidence_foundation
Revises: 0001_phase1_baseline
Create Date: 2026-09-04

BHUMI_FORENSICS_SPEC.md §3.1 / §3.4. Replaces the mutable `ocr_results` and
`extracted_fields` tables with an append-only evidence layer:

  ocr_results      -> ocr_runs        (+ is_current, status, error_message)
  extracted_fields -> claims          (+ evidence_region_id, lifecycle_status,
                                         asserted_by, supersedes_claim_id)
  (new)            -> evidence_regions (every OCR word region, not just the
                                         ones a value happened to match)

Written to be safe on two starting points, same as 0001:

  a) A database that has never run `alembic upgrade head` before Phase 2 was
     written: `app.models` now registers OcrRun/EvidenceRegion/Claim instead
     of OCRResult/ExtractedField, so 0001's own `Base.metadata.create_all()`
     already created `ocr_runs`, `evidence_regions` and `claims` directly —
     `ocr_results`/`extracted_fields` were never created. This migration then
     has nothing to create and nothing to migrate; it is a no-op.

  b) A database that already ran the old 0001 against the Phase 1 codebase,
     so `ocr_results` and `extracted_fields` exist with real rows: this
     migration creates the three new tables, copies every row forward
     (nothing is destroyed — BHUMI_FORENSICS_SPEC §2 rule 4), marks the
     migrated rows as the current state, and then drops the old tables.
"""
import json
from typing import Any, Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.database.base import Base
import app.models  # noqa: F401  (registers OcrRun/EvidenceRegion/Claim on Base.metadata)

revision: str = "0002_phase2_evidence_foundation"
down_revision: Union[str, None] = "0001_phase1_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_text(v: Any) -> Union[str, None]:
    """Normalise a JSON-ish column value read via raw SQL to a JSON text
    string suitable for a raw bind param on both SQLite (TEXT storage) and
    Postgres (json/jsonb accepts a JSON text literal). Handles the value
    arriving either already-decoded (dict/list, e.g. some DBAPI drivers
    auto-decode json/jsonb) or as the raw stored string.
    """
    if v is None:
        return None
    if isinstance(v, str):
        return v if v.strip() else None
    return json.dumps(v)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Create ocr_runs / evidence_regions / claims if they don't exist yet.
    Base.metadata.create_all(bind=bind, checkfirst=True)
    existing_tables = set(sa.inspect(bind).get_table_names())

    had_old_ocr = "ocr_results" in existing_tables
    had_old_fields = "extracted_fields" in existing_tables

    # 2. Migrate ocr_results -> ocr_runs, preserving every row.
    if had_old_ocr:
        old_cols = {c["name"] for c in sa.inspect(bind).get_columns("ocr_results")}
        select_cols = ", ".join(
            c for c in (
                "id", "document_id", "page_number", "raw_text", "layout_blocks",
                "detected_language", "average_confidence", "engine_used",
                "engine_version", "engine_languages", "word_count",
                "page_width", "page_height", "created_at",
            ) if c in old_cols
        )
        rows = list(bind.execute(sa.text(f"SELECT {select_cols} FROM ocr_results")))
        # id_map lets the claims migration below point evidence_region_id at
        # the right run indirectly (claims reference OCR by document+page,
        # not by the old ocr_results.id, so no id_map is needed here — this
        # loop only needs to preserve which row was newest per page).
        by_doc_page = {}
        for r in rows:
            m = dict(r._mapping)
            key = (m["document_id"], m.get("page_number", 1))
            by_doc_page.setdefault(key, []).append(m)

        for (doc_id, page_no), page_rows in by_doc_page.items():
            # created_at may be NULL on very old rows; fall back to id order.
            page_rows.sort(key=lambda m: (m.get("created_at") or "", m["id"]))
            for i, m in enumerate(page_rows):
                is_current = i == len(page_rows) - 1
                bind.execute(
                    sa.text(
                        """
                        INSERT INTO ocr_runs
                            (document_id, page_number, raw_text, layout_blocks,
                             detected_language, average_confidence, engine_used,
                             engine_version, engine_languages, params_json, word_count,
                             page_width, page_height, status, is_current,
                             started_at, finished_at, created_at)
                        VALUES
                            (:document_id, :page_number, :raw_text, :layout_blocks,
                             :detected_language, :average_confidence, :engine_used,
                             :engine_version, :engine_languages, :params_json, :word_count,
                             :page_width, :page_height, :status, :is_current,
                             :ts, :ts, :ts)
                        """
                    ),
                    {
                        "document_id": m["document_id"],
                        "page_number": m.get("page_number", 1),
                        "raw_text": m.get("raw_text", ""),
                        "layout_blocks": _json_text(m.get("layout_blocks")),
                        "detected_language": m.get("detected_language"),
                        "average_confidence": m.get("average_confidence"),
                        "engine_used": m.get("engine_used", "unknown"),
                        "engine_version": m.get("engine_version"),
                        "engine_languages": m.get("engine_languages"),
                        "params_json": None,
                        "word_count": m.get("word_count"),
                        "page_width": m.get("page_width"),
                        "page_height": m.get("page_height"),
                        "status": "SUCCEEDED",
                        "is_current": is_current,
                        "ts": m.get("created_at"),
                    },
                )

    # 3. Migrate extracted_fields -> claims, preserving every row. Regions are
    #    NOT reconstructed from old rows (the old schema only kept the winning
    #    bbox per field, not the full OCR word list this migration would need
    #    to identify a specific EvidenceRegion) — migrated claims carry their
    #    bounding_box forward exactly as before but evidence_region_id is left
    #    NULL. New processing runs after this migration populate it fully.
    if had_old_fields:
        old_cols = {c["name"] for c in sa.inspect(bind).get_columns("extracted_fields")}
        select_cols = ", ".join(
            c for c in (
                "id", "document_id", "field_name", "standardized_field", "field_value",
                "original_value", "translated_value", "transliteration", "translations_json",
                "confidence", "confidence_basis", "confidence_breakdown", "source_text",
                "page_number", "bounding_box", "bbox_source", "provenance", "status",
            ) if c in old_cols
        )
        rows = list(bind.execute(sa.text(f"SELECT {select_cols} FROM extracted_fields")))
        for r in rows:
            m = dict(r._mapping)
            bind.execute(
                sa.text(
                    """
                    INSERT INTO claims
                        (document_id, field_name, standardized_field, field_value,
                         original_value, translated_value, transliteration, translations_json,
                         confidence, confidence_basis, confidence_breakdown, source_text,
                         page_number, bounding_box, bbox_source, evidence_region_id,
                         extraction_method, extractor_version, provenance, status,
                         lifecycle_status, asserted_by, officer_id, supersedes_claim_id, created_at)
                    VALUES
                        (:document_id, :field_name, :standardized_field, :field_value,
                         :original_value, :translated_value, :transliteration, :translations_json,
                         :confidence, :confidence_basis, :confidence_breakdown, :source_text,
                         :page_number, :bounding_box, :bbox_source, NULL,
                         :extraction_method, 'phase1-migrated', :provenance, :status,
                         'ACCEPTED', :asserted_by, NULL, NULL, :ts)
                    """
                ),
                {
                    "document_id": m["document_id"],
                    "field_name": m.get("field_name", m.get("standardized_field", "")),
                    "standardized_field": m.get("standardized_field", ""),
                    "field_value": m.get("field_value"),
                    "original_value": m.get("original_value"),
                    "translated_value": m.get("translated_value"),
                    "transliteration": m.get("transliteration"),
                    "translations_json": _json_text(m.get("translations_json")),
                    "confidence": m.get("confidence"),
                    "confidence_basis": m.get("confidence_basis"),
                    "confidence_breakdown": _json_text(m.get("confidence_breakdown")),
                    "source_text": m.get("source_text"),
                    "page_number": m.get("page_number"),
                    "bounding_box": _json_text(m.get("bounding_box")),
                    "bbox_source": m.get("bbox_source") or "NONE",
                    "extraction_method": (
                        "MANUAL" if m.get("provenance") == "OFFICER_CORRECTION" else "REGEX_RULE"
                    ),
                    "provenance": m.get("provenance") or "DOCUMENT_OCR",
                    "status": m.get("status") or "auto_extracted",
                    "asserted_by": "OFFICER" if m.get("provenance") == "OFFICER_CORRECTION" else "SYSTEM",
                    "ts": None,
                },
            )

    # 4. Old tables are now fully superseded by the append-only ones. Nothing
    #    is lost — every row was copied forward in steps 2-3.
    if had_old_ocr:
        op.drop_table("ocr_results")
    if had_old_fields:
        op.drop_table("extracted_fields")


def downgrade() -> None:
    # The old mutable tables are gone by design; recreating them would need to
    # collapse append-only history back into single rows, which is lossy.
    # Phase 2 is not designed to be downgraded — restore from a backup taken
    # before this migration if a rollback is required.
    raise NotImplementedError(
        "0002_phase2_evidence_foundation is not downgradable — it would lose "
        "claim supersession history. Restore from a pre-migration backup."
    )
