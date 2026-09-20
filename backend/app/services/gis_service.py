from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.gis import GISParcel

class GISService:
    def get_all_parcels(
        self,
        db: Session,
        village: Optional[str] = None,
        district: Optional[str] = None,
        verified_only: bool = False,
    ) -> Dict[str, Any]:
        """Returns GeoJSON FeatureCollection of all cadastral parcels.

        `verified_only` restricts to verification_status == "verified" -- the
        public/citizen viewer's view, mirroring the same filter already
        applied to /records for that role. Staff calls pass False (the
        default) and see every parcel, unchanged.
        """
        query = db.query(GISParcel)
        if verified_only:
            query = query.filter(GISParcel.verification_status == "verified")
        if village:
            query = query.filter(GISParcel.village == village)
        if district:
            query = query.filter(GISParcel.district == district)

        parcels = query.all()
        features = []

        for p in parcels:
            features.append({
                "type": "Feature",
                "id": p.id,
                "properties": {
                    "id": p.id,
                    "khasra_number": p.khasra_number,
                    "khata_number": p.khata_number,
                    "owner_name": p.owner_name,
                    "area": p.area,
                    "area_unit": p.area_unit,
                    "village": p.village,
                    "tehsil": p.tehsil,
                    "district": p.district,
                    "state": p.state,
                    "land_classification": p.land_classification,
                    "verification_status": p.verification_status,
                    # Provenance travels with the geometry so the map can label
                    # synthetic parcels rather than implying they are surveyed.
                    "source_class": p.source_class,
                },
                "geometry": p.geometry_geojson
            })

        return {
            "type": "FeatureCollection",
            "features": features
        }

    def search_parcels(self, db: Session, query_str: str, verified_only: bool = False) -> List[Dict[str, Any]]:
        """Search parcels by Khasra, Khata, Owner, or Village."""
        q = f"%{query_str.strip()}%"
        query = db.query(GISParcel).filter(
            (GISParcel.khasra_number.ilike(q)) |
            (GISParcel.khata_number.ilike(q)) |
            (GISParcel.owner_name.ilike(q)) |
            (GISParcel.village.ilike(q))
        )
        if verified_only:
            query = query.filter(GISParcel.verification_status == "verified")
        parcels = query.limit(20).all()

        return [
            {
                "id": p.id,
                "khasra_number": p.khasra_number,
                "khata_number": p.khata_number,
                "owner_name": p.owner_name,
                "area": p.area,
                "area_unit": p.area_unit,
                "village": p.village,
                "district": p.district,
                "verification_status": p.verification_status,
                "source_class": p.source_class,
                "centroid": p.centroid_geojson,
            }
            for p in parcels
        ]

gis_service = GISService()
