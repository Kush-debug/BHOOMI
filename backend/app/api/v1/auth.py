from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.auth.jwt import verify_password, create_access_token
from app.schemas.auth import Token, UserResponse, LoginRequest
from app.config import settings
from app.services.audit_service import audit_service

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/login", response_model=Token)
def login(login_data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(
        (User.username == login_data.username) | (User.email == login_data.username)
    ).first()
    if not user or not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account. Contact administrator."
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=user.username, expires_delta=access_token_expires
    )

    audit_service.log_event(
        db,
        action="USER_LOGIN",
        user_id=user.id,
        details={"username": user.username, "role": user.role}
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "department": user.department,
            "state": user.state,
            "district": user.district,
            "tehsil": user.tehsil
        }
    }

@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    audit_service.log_event(
        db,
        action="USER_LOGOUT",
        user_id=current_user.id,
        details={"username": current_user.username}
    )
    return {"status": "success", "message": "Logged out successfully"}

@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/roles")
def list_roles(current_user: User = Depends(get_current_user)):
    """Role catalogue. Authenticated: only the login endpoint is public."""
    return [
        {"role": "super_admin", "title": "Super Administrator", "desc": "Top-level central administration, system oversight & security policy"},
        {"role": "admin", "title": "State Administrator", "desc": "Full state management, configuration & user administration"},
        {"role": "district_officer", "title": "District Magistrate / Collector", "desc": "District-level monitoring, audits & reports"},
        {"role": "tehsil_officer", "title": "Tehsildar / Sub-Divisional Magistrate", "desc": "Tehsil land records approval & management"},
        {"role": "verification_officer", "title": "Verification Officer / Revenue Inspector", "desc": "Document digitization, AI field validation & correction"},
        {"role": "viewer", "title": "Public / Citizen Viewer", "desc": "Read-only access to verified land registry & GIS map"}
    ]
