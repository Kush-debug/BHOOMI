from datetime import datetime
import uuid
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from app.database.base import Base

class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    document_uuid = Column(String(36), default=lambda: str(uuid.uuid4()), unique=True, index=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)
    mime_type = Column(String(100), default="application/pdf")
    sha256 = Column(String(64), nullable=True, index=True)  # duplicate-upload detection
    page_count = Column(Integer, nullable=True)

    # Data provenance. Real uploads must never be mixed with synthetic demo data
    # in statistics or in the UI (BHUMI_FORENSICS_SPEC §2 rule 5).
    source_class = Column(String(20), default="REAL_UPLOAD", index=True)
    # REAL_UPLOAD | SEED_SYNTHETIC | EXTERNAL_IMPORT
    
    # Metadata
    state = Column(String(100), nullable=False, default="Uttar Pradesh")
    district = Column(String(100), nullable=False, default="Kanpur Nagar")
    tehsil = Column(String(100), nullable=False, default="Bilhaur")
    village = Column(String(150), nullable=False, default="Bilhaur Dehat")
    document_type = Column(String(50), default="khasra_b1")
    document_year = Column(Integer, default=2024)
    
    # Multilingual & Auto Detection
    language = Column(String(20), default="hi")  # requested or fallback lang
    detected_language = Column(String(20), default="hi")  # automatically detected language code: ta, te, kn, hi, en, etc.
    detected_language_name = Column(String(50), default="Hindi")
    target_language = Column(String(20), default="en")  # user-selected translation target
    
    # Detailed Multi-dimensional Confidence Metrics
    language_confidence = Column(Float, nullable=True, default=None)
    ocr_confidence = Column(Float, nullable=True, default=None)
    extraction_confidence = Column(Float, nullable=True, default=None)
    translation_confidence = Column(Float, nullable=True, default=None)
    validation_confidence = Column(Float, nullable=True, default=None)
    
    # Text Preservation
    original_ocr_text = Column(Text, nullable=True)
    translated_text = Column(Text, nullable=True)
    
    # Status & Workflow
    status = Column(String(50), default="uploaded", index=True)  # uploaded, processing, processed, verification_pending, verified, rejected, failed
    validation_status = Column(String(50), default="pending")  # pending, valid, warning, failed, requires_verification, verified

    # Populated when a processing stage raises. Surfaced verbatim to the officer
    # instead of substituting invented output.
    processing_error_code = Column(String(64), nullable=True)
    processing_error_message = Column(Text, nullable=True)
    processing_failed_stage = Column(String(32), nullable=True)
    
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    #
    # `_ocr_runs_all` / `_claims_all` carry every row ever written — including
    # retired OCR runs and superseded claims — so a document delete correctly
    # cascades to its full evidence history (BHUMI_FORENSICS_SPEC §3.1: append-
    # only, never destroyed). `ocr_results` and `extracted_fields` are plain
    # Python properties below that filter those down to the CURRENT rows —
    # the same attribute names and the same filtered shape every existing
    # endpoint, schema and frontend call site already expected before Phase 2
    # made the underlying tables append-only.
    pages = relationship("DocumentPage", back_populates="document", cascade="all, delete-orphan")
    _ocr_runs_all = relationship("OcrRun", back_populates="document", cascade="all, delete-orphan")
    _claims_all = relationship("Claim", back_populates="document", cascade="all, delete-orphan")
    validation_results = relationship("ValidationResult", back_populates="document", cascade="all, delete-orphan")
    land_record = relationship("LandRecord", back_populates="document", uselist=False, cascade="all, delete-orphan")

    @property
    def ocr_results(self):
        """Current OCR runs only (is_current=True) — retired reprocessing runs are excluded."""
        return [r for r in self._ocr_runs_all if r.is_current]

    @property
    def extracted_fields(self):
        """Current claims only (lifecycle_status=ACCEPTED) — superseded/rejected claims are excluded."""
        return [c for c in self._claims_all if c.lifecycle_status == "ACCEPTED"]

class DocumentPage(Base):
    __tablename__ = "document_pages"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number = Column(Integer, default=1)
    original_image_path = Column(String(500), nullable=False)
    preprocessed_image_path = Column(String(500), nullable=True)
    width = Column(Integer, default=0)
    height = Column(Integer, default=0)

    document = relationship("Document", back_populates="pages")
