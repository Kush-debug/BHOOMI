from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.base import Base

class ValidationResult(Base):
    __tablename__ = "validation_results"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    record_id = Column(Integer, ForeignKey("land_records.id", ondelete="CASCADE"), nullable=True)
    validation_type = Column(String(50), nullable=False)  # rule_based, cross_database, duplicate_check, hierarchy_check
    rule_name = Column(String(100), nullable=False)
    severity = Column(String(20), default="warning")  # error, warning, info
    status = Column(String(20), default="failed")  # failed, passed, resolved
    field_name = Column(String(100), nullable=True)
    expected_value = Column(String(255), nullable=True)
    actual_value = Column(String(255), nullable=True)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="validation_results")

class MasterLocation(Base):
    __tablename__ = "master_locations"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String(50), nullable=False, index=True)
    district = Column(String(50), nullable=False, index=True)
    tehsil = Column(String(50), nullable=False, index=True)
    village = Column(String(100), nullable=False, index=True)
    village_code = Column(String(50), nullable=True)
    pincode = Column(String(10), nullable=True)

class MasterLandRegistry(Base):
    """Authoritative Government Database used for Cross-Database Validation"""
    __tablename__ = "master_land_registry"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String(50), nullable=False, index=True)
    district = Column(String(50), nullable=False, index=True)
    tehsil = Column(String(50), nullable=False, index=True)
    village = Column(String(100), nullable=False, index=True)
    khasra_number = Column(String(50), nullable=False, index=True)
    khata_number = Column(String(50), nullable=False, index=True)
    owner_name = Column(String(200), nullable=False, index=True)
    father_name = Column(String(200), nullable=True)
    area = Column(Float, nullable=False)
    area_unit = Column(String(30), default="hectare")
    land_classification = Column(String(100), default="Agricultural")
