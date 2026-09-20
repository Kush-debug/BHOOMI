from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.auth.rbac import CAN_READ_FINDINGS, CAN_RESOLVE_FINDINGS, require_roles
from app.models.user import User
from app.services.audit_service import audit_service
from app.models.validation import ValidationResult, MasterLocation
from app.models.document import Document
from app.schemas.validation import ValidationResultResponse, MasterLocationResponse

router = APIRouter(prefix="/validation", tags=["Validation & Anomalies"])

@router.get("/anomalies", response_model=List[ValidationResultResponse])
def get_all_anomalies(
    severity: Optional[str] = None,
    validation_type: Optional[str] = None,
    status: Optional[str] = "failed",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_FINDINGS)),
):
    query = db.query(ValidationResult)
    if severity:
        query = query.filter(ValidationResult.severity == severity)
    if validation_type:
        query = query.filter(ValidationResult.validation_type == validation_type)
    if status:
        query = query.filter(ValidationResult.status == status)

    return query.order_by(ValidationResult.created_at.desc()).all()

@router.put("/resolve/{id}")
def resolve_anomaly(
    id: int,
    reason: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_RESOLVE_FINDINGS)),
):
    """Resolving a finding is an officer decision. It requires a reason and is audited.

    This endpoint was previously unauthenticated: anyone could silently clear a
    detected anomaly (ARCHITECTURE_AUDIT §4.3).
    """
    anom = db.query(ValidationResult).filter(ValidationResult.id == id).first()
    if not anom:
        raise HTTPException(status_code=404, detail="Finding not found")
    if not reason.strip():
        raise HTTPException(status_code=422, detail="A reason is required to resolve a finding.")
    anom.status = "resolved"
    db.commit()
    audit_service.log_event(
        db,
        action="FINDING_RESOLVED",
        user_id=current_user.id,
        document_id=anom.document_id,
        details={"finding_id": id, "rule": anom.rule_name, "reason": reason},
    )
    return {"message": "Finding marked as resolved", "finding_id": id}

@router.get("/locations", response_model=List[MasterLocationResponse])
def get_master_locations(
    state: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_FINDINGS)),
):
    query = db.query(MasterLocation)
    if state:
        query = query.filter(MasterLocation.state == state)
    return query.all()
