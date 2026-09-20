from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

class GISParcelResponse(BaseModel):
    id: int
    state: str
    district: str
    tehsil: str
    village: str
    khasra_number: str
    khata_number: str
    owner_name: str
    area: float
    area_unit: str
    land_classification: str
    verification_status: str
    source_class: str = "SEED_SYNTHETIC"
    geometry_geojson: Dict[str, Any]
    centroid_geojson: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True

class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[Dict[str, Any]]
