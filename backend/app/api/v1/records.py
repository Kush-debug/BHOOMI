import csv
import io
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.auth.rbac import (
    CAN_EXPORT_REGISTRY,
    CAN_READ_REGISTRY,
    STAFF_ROLES,
    VIEWER,
    require_roles,
)
from app.models.user import User
from app.services.audit_service import audit_service
from app.models.record import LandRecord
from app.models.training import VerificationRecord
from app.schemas.record import LandRecordResponse, LandRecordUpdate, ViewerLandRecordResponse

router = APIRouter(prefix="/records", tags=["Land Records Registry"])

@router.get("/", response_model=None)
def list_land_records(
    search: Optional[str] = None,
    state: Optional[str] = None,
    district: Optional[str] = None,
    tehsil: Optional[str] = None,
    village: Optional[str] = None,
    khasra_number: Optional[str] = None,
    khata_number: Optional[str] = None,
    verification_status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_REGISTRY)),
):
    query = db.query(LandRecord)
    # Public/citizen viewers only ever see records a human has verified.
    if current_user.role == VIEWER:
        query = query.filter(LandRecord.verification_status == "verified")
    if state:
        query = query.filter(LandRecord.state == state)
    if district:
        query = query.filter(LandRecord.district == district)
    if tehsil:
        query = query.filter(LandRecord.tehsil == tehsil)
    if village:
        query = query.filter(LandRecord.village == village)
    if khasra_number:
        query = query.filter(LandRecord.khasra_number == khasra_number)
    if khata_number:
        query = query.filter(LandRecord.khata_number == khata_number)
    if verification_status:
        query = query.filter(LandRecord.verification_status == verification_status)
    if search:
        s = f"%{search.strip()}%"
        query = query.filter(
            (LandRecord.owner_name.ilike(s)) |
            (LandRecord.khasra_number.ilike(s)) |
            (LandRecord.khata_number.ilike(s)) |
            (LandRecord.village.ilike(s)) |
            (LandRecord.mutation_number.ilike(s)) |
            (LandRecord.registration_number.ilike(s))
        )

    results = (
        query.order_by(LandRecord.created_at.desc())
        .offset(max(0, offset))
        .limit(min(max(1, limit), 500))
        .all()
    )
    # response_model is deliberately unset on this route: the schema itself
    # differs by role (see ViewerLandRecordResponse's docstring), not just
    # which rows are visible. Staff serialization is untouched.
    if current_user.role == VIEWER:
        return [ViewerLandRecordResponse.model_validate(r) for r in results]
    return [LandRecordResponse.model_validate(r) for r in results]

@router.get("/export/csv")
def export_land_records_csv(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_EXPORT_REGISTRY)),
):
    # Bulk export of personal data. Restricted, and always audited.
    records = db.query(LandRecord).all()
    audit_service.log_event(
        db,
        action="REGISTRY_EXPORTED_CSV",
        user_id=current_user.id,
        details={"record_count": len(records)},
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Record ID", "State", "District", "Tehsil", "Village",
        "Khasra No", "Khata No", "Owner Name", "Father Name",
        "Area", "Unit", "Land Class", "Status", "Verified Date"
    ])
    for r in records:
        writer.writerow([
            r.id, r.state, r.district, r.tehsil, r.village,
            r.khasra_number, r.khata_number, r.owner_name, r.father_name or "",
            r.area, r.area_unit, r.land_classification, r.verification_status,
            r.verified_at.strftime("%Y-%m-%d %H:%M") if r.verified_at else "Pending"
        ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bhoomi_land_records.csv"}
    )

@router.get("/{id}", response_model=None)
def get_land_record(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_REGISTRY)),
):
    record = db.query(LandRecord).filter(LandRecord.id == id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Land Record not found")
    if current_user.role == VIEWER and record.verification_status != "verified":
        raise HTTPException(status_code=404, detail="Land Record not found")
    if current_user.role == VIEWER:
        return ViewerLandRecordResponse.model_validate(record)
    return LandRecordResponse.model_validate(record)

@router.get("/{id}/history")
def get_record_history(
    id: int,
    db: Session = Depends(get_db),
    # Internal verification workflow trail (which officer acted, their
    # notes). Not part of the viewer's feature set -- see
    # ViewerLandRecordResponse and the record detail endpoint above for what
    # a viewer gets instead.
    current_user: User = Depends(require_roles(STAFF_ROLES)),
):
    record = db.query(LandRecord).filter(LandRecord.id == id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Land Record not found")

    verifications = db.query(VerificationRecord).filter(
        VerificationRecord.record_id == id
    ).order_by(VerificationRecord.created_at.desc()).all()

    return {
        "record_id": record.id,
        "khasra_number": record.khasra_number,
        "owner_name": record.owner_name,
        "timeline": [
            {
                "id": v.id,
                "action": v.action,
                "verifier_id": v.verifier_id,
                "notes": v.notes,
                "created_at": v.created_at,
                "previous_state": v.previous_state,
                "new_state": v.new_state
            }
            for v in verifications
        ]
    }
