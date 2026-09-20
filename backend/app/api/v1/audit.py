from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.auth.rbac import CAN_READ_AUDIT, require_roles
from app.models.user import User
from app.models.audit import AuditLog
from app.schemas.common import AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit Trail"])

@router.get("/logs", response_model=List[AuditLogResponse])
def get_audit_logs(
    action: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(CAN_READ_AUDIT)),
):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action}%"))
    return (
        query.order_by(AuditLog.timestamp.desc())
        .offset(max(0, offset))
        .limit(min(max(1, limit), 500))
        .all()
    )
