from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Text, Boolean
from app.database.base import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=True)
    record_id = Column(Integer, ForeignKey("land_records.id"), nullable=True)
    action = Column(String(100), nullable=False)  # UPLOAD, OCR_PROCESSED, FIELD_EDITED, RECORD_APPROVED, RECORD_REJECTED
    details = Column(JSON, default=dict)
    ip_address = Column(String(50), default="127.0.0.1")
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    type = Column(String(30), default="info")  # alert, warning, success, info
    link = Column(String(255), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
