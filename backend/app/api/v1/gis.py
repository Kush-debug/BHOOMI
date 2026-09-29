import os
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.auth.rbac import CAN_READ_GIS, CAN_WRITE_GIS, VIEWER, require_roles
from app.models.user import User
from app.services.audit_service import audit_service
from app.models.gis import GISParcel
from app.schemas.gis import GISParcelResponse, GeoJSONFeatureCollection
from app.services.gis_service import gis_service
from app.services.cadastral_map_service import cadastral_map_service
from app.config import settings

router = APIRouter(prefix="/gis", tags=["GIS & Cadastral Mapping"])

@router.get("/parcels", response_model=GeoJSONFeatureCollection)
def get_cadastral_parcels(
    village: Optional[str] = None,
    district: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_GIS)),
):
    """Cadastral parcels as GeoJSON.

    Each feature carries `source_class`, so synthetic demo geometry is never
    displayed as if it were surveyed cadastral data. The public/citizen
    viewer only ever sees parcels a human has verified -- same rule as
    /records, applied here too since GIS geometry is otherwise open to
    every role.
    """
    return gis_service.get_all_parcels(
        db, village=village, district=district, verified_only=current_user.role == VIEWER
    )

@router.get("/parcels/{id}", response_model=GISParcelResponse)
def get_parcel(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_GIS)),
):
    parcel = db.query(GISParcel).filter(GISParcel.id == id).first()
    if not parcel:
        raise HTTPException(status_code=404, detail="GIS Parcel not found")
    if current_user.role == VIEWER and parcel.verification_status != "verified":
        raise HTTPException(status_code=404, detail="GIS Parcel not found")
    return parcel

@router.get("/search")
def search_parcels(
    q: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_GIS)),
):
    return gis_service.search_parcels(db, q, verified_only=current_user.role == VIEWER)

@router.post("/vectorize-map")
async def vectorize_cadastral_map(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_WRITE_GIS)),
):
    """Detect parcel outlines in a scanned village map sheet.

    IMPORTANT: the output is NOT georeferenced. Contours are detected in image
    pixel space; without survey control points they cannot be placed on the earth.
    Every feature is returned with `geometry_source: VECTORIZED_UNGEOREFERENCED`
    and must be presented as a tracing aid, not as cadastral boundaries.
    """
    import os
    import re as _re

    allowed = {".png", ".jpg", ".jpeg", ".tif", ".tiff"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Map sheet must be an image ({', '.join(sorted(allowed))}).",
        )

    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Map sheet exceeds the upload size limit.")

    # Never build a path from an untrusted filename.
    safe_stem = _re.sub(r"[^A-Za-z0-9_.-]", "_", os.path.basename(file.filename or "map"))[:80]
    temp_path = settings.UPLOAD_DIR / f"cadastral_{current_user.id}_{safe_stem}"
    with open(temp_path, "wb") as f:
        f.write(content)

    result = cadastral_map_service.process_cadastral_map(str(temp_path))
    audit_service.log_event(
        db,
        action="CADASTRAL_MAP_VECTORIZED",
        user_id=current_user.id,
        details={"file_name": file.filename, "parcels_detected": result.get("parcels_detected")},
    )
    return result
