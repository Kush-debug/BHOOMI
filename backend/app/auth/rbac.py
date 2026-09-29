"""
Authentication dependency and role-based access control.

Every domain route is gated. Before this change 30 of 45 endpoints were fully
public, including bulk registry export, the audit trail, and anomaly resolution
(ARCHITECTURE_AUDIT §4.3).
"""
from typing import List

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.jwt import decode_access_token
from app.database.session import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

# --- Roles -------------------------------------------------------------------

SUPER_ADMIN = "super_admin"
ADMIN = "admin"
DISTRICT_OFFICER = "district_officer"
TEHSIL_OFFICER = "tehsil_officer"
VERIFICATION_OFFICER = "verification_officer"
VIEWER = "viewer"

ALL_ROLES = [SUPER_ADMIN, ADMIN, DISTRICT_OFFICER, TEHSIL_OFFICER, VERIFICATION_OFFICER, VIEWER]
STAFF_ROLES = [SUPER_ADMIN, ADMIN, DISTRICT_OFFICER, TEHSIL_OFFICER, VERIFICATION_OFFICER]
SENIOR_ROLES = [SUPER_ADMIN, ADMIN, DISTRICT_OFFICER, TEHSIL_OFFICER]

ROLE_HIERARCHY = {
    SUPER_ADMIN: ALL_ROLES,
    ADMIN: [ADMIN, DISTRICT_OFFICER, TEHSIL_OFFICER, VERIFICATION_OFFICER, VIEWER],
    DISTRICT_OFFICER: [DISTRICT_OFFICER, TEHSIL_OFFICER, VERIFICATION_OFFICER, VIEWER],
    TEHSIL_OFFICER: [TEHSIL_OFFICER, VERIFICATION_OFFICER, VIEWER],
    VERIFICATION_OFFICER: [VERIFICATION_OFFICER, VIEWER],
    VIEWER: [VIEWER],
}

# --- Capability groups -------------------------------------------------------
# Named by what they permit, so route decorators read as policy, not as role lists.

CAN_UPLOAD = STAFF_ROLES
CAN_PROCESS = STAFF_ROLES
CAN_READ_DOCUMENTS = STAFF_ROLES              # scans may contain personal data
CAN_DELETE_DOCUMENTS = [SUPER_ADMIN, ADMIN]
CAN_VERIFY = STAFF_ROLES                       # open a document in the workspace
CAN_APPROVE_RECORD = STAFF_ROLES               # submit approve / reject
CAN_READ_REGISTRY = ALL_ROLES                  # viewers are restricted to verified records
CAN_EXPORT_REGISTRY = SENIOR_ROLES
CAN_READ_FINDINGS = STAFF_ROLES
CAN_RESOLVE_FINDINGS = STAFF_ROLES
CAN_MANAGE_INVESTIGATIONS = STAFF_ROLES        # assign / comment / resolve an InvestigationCase (Phase 7)
CAN_READ_AUDIT = [SUPER_ADMIN, ADMIN, DISTRICT_OFFICER]
CAN_READ_ANALYTICS = STAFF_ROLES
CAN_READ_GIS = ALL_ROLES
CAN_WRITE_GIS = SENIOR_ROLES
CAN_READ_LEARNING = STAFF_ROLES
CAN_READ_LOCATIONS = ALL_ROLES
CAN_ADMINISTER = [SUPER_ADMIN, ADMIN]


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception
    username = payload.get("sub")
    if not username:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated. Please contact your administrator.",
        )
    return user


def require_roles(allowed_roles: List[str]):
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role == SUPER_ADMIN:
            return current_user
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. This action requires one of: {', '.join(allowed_roles)}.",
            )
        return current_user

    return role_checker
