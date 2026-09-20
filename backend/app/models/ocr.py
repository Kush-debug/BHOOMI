"""
Evidence layer (BHUMI_FORENSICS_SPEC.md §3.1 — Phase 2: Evidence foundation).

Three tables, in dependency order:

  OcrRun          One row per (document, page, engine execution). APPEND-ONLY —
                   reprocessing a page never deletes the old run, it adds a new
                   one and flips `is_current` on the previous run to 0. This is
                   what makes "what did OCR actually see on this page, and when"
                   an auditable history instead of a value that gets clobbered.

  EvidenceRegion   Every OCR word region a run produced, with its real bounding
                   box and confidence — not just the words that happened to
                   match an extracted value. This is the full, queryable output
                   of OCR, and it is what a Claim points back to.

  Claim            A predicate/value pair asserted about a document (e.g.
                   "owner_name = Ram Prasad"). Claims are immutable once
                   written: correcting one never edits it in place — it creates
                   a NEW Claim row with `supersedes_claim_id` set to the old
                   one, and flips the old row's `lifecycle_status` to
                   SUPERSEDED. Both rows stay queryable forever, so an officer
                   correction is always distinguishable from the original
                   AI-extracted value (BHUMI_FORENSICS_SPEC.md §2 rule 4).

Column names on Claim intentionally mirror the old `ExtractedField` model
(`standardized_field`, `field_value`, `bounding_box`, `bbox_source`,
`provenance`, `status`) so the existing API response shape and frontend need
no changes. What changed underneath is real: regions are now persisted as
first-class rows, runs are append-only, and corrections supersede rather than
overwrite. See PHASE2_CHANGES.md for the full rationale and the API surface
this unlocks (`/documents/{id}/claims`, `/documents/{id}/regions`,
`/claims/{id}/evidence`).
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from app.database.base import Base


class OcrRun(Base):
    __tablename__ = "ocr_runs"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, default=1, index=True)

    raw_text = Column(Text, nullable=False)
    layout_blocks = Column(JSON, default=list)  # full raw word list: [{type, bbox, text, confidence, line_num, word_num}]
    detected_language = Column(String(20), default="hi")
    average_confidence = Column(Float, nullable=True, default=None)
    engine_used = Column(String(50), nullable=False)
    engine_version = Column(String(50), nullable=True)
    engine_languages = Column(String(100), nullable=True)
    params_json = Column(JSON, default=dict)
    word_count = Column(Integer, default=0)
    page_width = Column(Integer, nullable=True)
    page_height = Column(Integer, nullable=True)

    status = Column(String(20), default="SUCCEEDED")  # SUCCEEDED | FAILED
    error_message = Column(Text, nullable=True)

    # Only the current run per (document_id, page_number) backs live claims.
    # Older runs are kept — never deleted — for audit and reprocessing history.
    is_current = Column(Boolean, default=True, index=True)

    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Pairs with Document._ocr_runs_all (the unfiltered cascade relationship).
    # Document.ocr_results is a separate filtered @property — see
    # app/models/document.py.
    document = relationship("Document", back_populates="_ocr_runs_all")
    regions = relationship("EvidenceRegion", back_populates="ocr_run", cascade="all, delete-orphan")


class EvidenceRegion(Base):
    __tablename__ = "evidence_regions"

    id = Column(Integer, primary_key=True, index=True)
    ocr_run_id = Column(Integer, ForeignKey("ocr_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, default=1, index=True)

    text = Column(String(500), nullable=False)
    bbox = Column(JSON, nullable=False)  # {x, y, w, h} in page-image pixels — always real, never a placeholder
    page_width = Column(Integer, nullable=True)
    page_height = Column(Integer, nullable=True)

    ocr_confidence = Column(Float, nullable=True, default=None)
    geometry_source = Column(String(20), default="OCR_WORD_BOX")  # OCR_WORD_BOX | OCR_LINE_BOX | MANUAL
    line_num = Column(Integer, nullable=True)
    word_num = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    ocr_run = relationship("OcrRun", back_populates="regions")
    document = relationship("Document")


class Claim(Base):
    """The evidence graph's edge. See module docstring for the supersession rule."""

    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)

    # Set by IdentityResolver (Phase 3) once the document's khasra/khata and
    # location resolve to a durable Parcel/Person. NULL until resolution
    # runs, or if resolution genuinely could not place this claim (e.g. no
    # khasra number was extracted at all).
    parcel_id = Column(Integer, ForeignKey("parcels.id"), nullable=True, index=True)
    person_id = Column(Integer, ForeignKey("persons.id"), nullable=True, index=True)

    field_name = Column(String(150), nullable=False)
    standardized_field = Column(String(100), nullable=False, index=True)  # owner_name, khasra_number, ...

    field_value = Column(String(500), nullable=True)
    original_value = Column(String(500), nullable=True)
    translated_value = Column(String(500), nullable=True)
    transliteration = Column(String(500), nullable=True)
    translations_json = Column(JSON, default=dict)

    confidence = Column(Float, nullable=True, default=None)  # NULL = not computable, never a filler value
    confidence_basis = Column(String(200), nullable=True)
    confidence_breakdown = Column(JSON, default=dict)

    source_text = Column(String(500), nullable=True)
    page_number = Column(Integer, default=1)

    # Denormalised copy of the winning region's geometry, for cheap reads
    # without a join. `evidence_region_id` below is the authoritative link
    # used by the /claims/{id}/evidence endpoint to walk back to the source.
    bounding_box = Column(JSON, nullable=True, default=None)
    bbox_source = Column(String(20), default="NONE")  # OCR_WORD_BOX | OCR_LINE_BOX | MANUAL | NONE
    evidence_region_id = Column(Integer, ForeignKey("evidence_regions.id", ondelete="SET NULL"), nullable=True)

    extraction_method = Column(String(20), default="REGEX_RULE")  # REGEX_RULE | MANUAL
    extractor_version = Column(String(20), nullable=True, default="phase2-regex-v1")

    provenance = Column(String(24), default="DOCUMENT_OCR")  # DOCUMENT_OCR | UPLOAD_METADATA | OFFICER_CORRECTION
    status = Column(String(50), default="auto_extracted")  # auto_extracted | edited | verified | from_upload_metadata

    # Supersession lifecycle — see module docstring. ACCEPTED is the only
    # status that participates in "current value" queries; SUPERSEDED and
    # REJECTED rows stay in the table for the audit trail.
    lifecycle_status = Column(String(20), default="ACCEPTED", index=True)  # ACCEPTED | SUPERSEDED | REJECTED
    asserted_by = Column(String(10), default="SYSTEM")  # SYSTEM | OFFICER
    officer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    supersedes_claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Pairs with Document._claims_all (the unfiltered cascade relationship).
    # Document.extracted_fields is a separate filtered @property — see
    # app/models/document.py.
    document = relationship("Document", back_populates="_claims_all")
    evidence_region = relationship("EvidenceRegion", foreign_keys=[evidence_region_id])
