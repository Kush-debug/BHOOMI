from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.database.base import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(50), default="viewer", nullable=False)  # super_admin, admin, district_officer, tehsil_officer, verification_officer, viewer
    department = Column(String(100), default="Revenue Department")
    state = Column(String(50), default="Uttar Pradesh")
    district = Column(String(50), default="Kanpur Nagar")
    tehsil = Column(String(50), default="Bilhaur")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
