from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text
from app.database.base import Base

class TrainingCorrection(Base):
    """Human-in-the-loop verified corrections for active learning & OCR/NER fine-tuning"""
    __tablename__ = "training_corrections"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    field_name = Column(String(100), nullable=False)
    original_value = Column(String(500), nullable=True)
    corrected_value = Column(String(500), nullable=False)
    document_type = Column(String(50), default="khasra_b1")
    language = Column(String(20), default="hi")
    bounding_box = Column(JSON, default=dict)
    verifier_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class VerificationRecord(Base):
    __tablename__ = "verification_records"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    record_id = Column(Integer, ForeignKey("land_records.id", ondelete="CASCADE"), nullable=True)
    verifier_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(50), nullable=False)  # approved, edited_approved, rejected, reprocessing_requested
    previous_state = Column(JSON, default=dict)
    new_state = Column(JSON, default=dict)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
