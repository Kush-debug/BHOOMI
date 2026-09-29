from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, JSON, Text
from sqlalchemy.orm import relationship
from app.database.base import Base

class LandRecord(Base):
    __tablename__ = "land_records"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    
    # Administrative Hierarchy
    state = Column(String(50), nullable=False, index=True)
    district = Column(String(50), nullable=False, index=True)
    tehsil = Column(String(50), nullable=False, index=True)
    village = Column(String(100), nullable=False, index=True)
    
    # Ownership Details
    owner_name = Column(String(200), nullable=False, index=True)
    father_name = Column(String(200), nullable=True)
    address = Column(String(500), nullable=True)
    ownership_type = Column(String(50), default="Individual")  # Individual, Joint, Government, Trust
    
    # Land Identifiers
    survey_number = Column(String(50), nullable=True, index=True)
    khasra_number = Column(String(50), nullable=False, index=True)
    khata_number = Column(String(50), nullable=False, index=True)
    plot_number = Column(String(50), nullable=True)
    
    # Extent & Classification
    area = Column(Float, nullable=False)
    area_unit = Column(String(30), default="hectare")  # hectare, acre, bigha, biswa, sq_meter
    land_classification = Column(String(100), default="Agricultural")  # Agricultural, Residential, Commercial, Forest, Pasture
    
    # Mutation & Registration
    mutation_number = Column(String(50), nullable=True, index=True)
    mutation_date = Column(Date, nullable=True)
    mutation_type = Column(String(100), nullable=True)  # Inheritance, Sale Deed, Partition, Gift
    registration_number = Column(String(50), nullable=True, index=True)
    registration_date = Column(Date, nullable=True)
    registration_office = Column(String(100), nullable=True)
    
    # Verification State
    verification_status = Column(String(50), default="pending", index=True)  # pending, verified, rejected, duplicate
    verified_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    verification_notes = Column(Text, nullable=True)
    
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    document = relationship("Document", back_populates="land_record")
