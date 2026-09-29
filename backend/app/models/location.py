from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.database.base import Base

class Country(Base):
    __tablename__ = "countries"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, default="India")
    code = Column(String(10), nullable=False, default="IN", unique=True)
    is_active = Column(Boolean, default=True)

    states = relationship("State", back_populates="country", cascade="all, delete-orphan")

class State(Base):
    __tablename__ = "states"

    id = Column(Integer, primary_key=True, index=True)
    country_id = Column(Integer, ForeignKey("countries.id"), nullable=False, default=1)
    name = Column(String(100), nullable=False, unique=True, index=True)
    code = Column(String(10), nullable=False, unique=True, index=True)
    type = Column(String(20), nullable=False, default="STATE")  # STATE or UNION_TERRITORY
    is_active = Column(Boolean, default=True)

    country = relationship("Country", back_populates="states")
    districts = relationship("District", back_populates="state", cascade="all, delete-orphan")

class District(Base):
    __tablename__ = "districts"

    id = Column(Integer, primary_key=True, index=True)
    state_id = Column(Integer, ForeignKey("states.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)

    state = relationship("State", back_populates="districts")
    tehsils = relationship("Tehsil", back_populates="district", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_district_state_name", "state_id", "name"),
    )

class Tehsil(Base):
    __tablename__ = "tehsils"

    id = Column(Integer, primary_key=True, index=True)
    district_id = Column(Integer, ForeignKey("districts.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True)

    district = relationship("District", back_populates="tehsils")
    villages = relationship("Village", back_populates="tehsil", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_tehsil_district_name", "district_id", "name"),
    )

class Village(Base):
    __tablename__ = "villages"

    id = Column(Integer, primary_key=True, index=True)
    tehsil_id = Column(Integer, ForeignKey("tehsils.id"), nullable=False, index=True)
    name = Column(String(150), nullable=False, index=True)
    village_code = Column(String(50), nullable=True)
    pincode = Column(String(10), nullable=True)
    is_active = Column(Boolean, default=True)

    tehsil = relationship("Tehsil", back_populates="villages")

    __table_args__ = (
        Index("idx_village_tehsil_name", "tehsil_id", "name"),
    )
