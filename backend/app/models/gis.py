from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON
from app.database.base import Base

class GISParcel(Base):
    __tablename__ = "gis_parcels"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String(50), nullable=False, index=True)
    district = Column(String(50), nullable=False, index=True)
    tehsil = Column(String(50), nullable=False, index=True)
    village = Column(String(100), nullable=False, index=True)
    khasra_number = Column(String(50), nullable=False, index=True)
    khata_number = Column(String(50), nullable=False, index=True)
    owner_name = Column(String(200), nullable=False)
    area = Column(Float, nullable=False)
    area_unit = Column(String(30), default="hectare")
    land_classification = Column(String(100), default="Agricultural")
    verification_status = Column(String(50), default="verified")  # verified, pending, disputed, mismatch
    
    # Provenance of the geometry. VECTORIZED_UNGEOREFERENCED polygons have no
    # survey control points and must never be presented as surveyed boundaries.
    source_class = Column(String(32), default="SEED_SYNTHETIC", index=True)
    # SURVEYED | VECTORIZED_UNGEOREFERENCED | SYNTHETIC_DEMO | SEED_SYNTHETIC

    geometry_geojson = Column(JSON, nullable=False)  # GeoJSON Feature/Polygon
    centroid_geojson = Column(JSON, nullable=True)   # GeoJSON Point [lng, lat]
    created_at = Column(DateTime, default=datetime.utcnow)
