from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.api.deps import get_db, get_current_user, require_roles
from app.models.user import User
from app.models.audit import AuditLog
from app.schemas.auth import (
    UserCreate,
    UserUpdate,
    UserStatusUpdate,
    UserPasswordReset,
    UserResponse,
    AdminStatsResponse
)
from app.auth.jwt import get_password_hash
from app.services.audit_service import audit_service

router = APIRouter(prefix="/admin", tags=["Admin Management"])

@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_dashboard_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin", "admin"]))
):
    total = db.query(User).count()
    active = db.query(User).filter(User.is_active == True).count()
    inactive = db.query(User).filter(User.is_active == False).count()

    # Roles distribution
    roles_counts = db.query(User.role, func.count(User.id)).group_by(User.role).all()
    roles_dist = {r[0]: r[1] for r in roles_counts}

    # Recent admin activity from audit logs
    recent_logs = db.query(AuditLog).filter(
        AuditLog.action.like("ADMIN_%") | AuditLog.action.like("USER_%") | AuditLog.action.like("PASSWORD_%")
    ).order_by(AuditLog.timestamp.desc()).limit(10).all()

    recent_activity = [
        {
            "id": log.id,
            "action": log.action,
            "user_id": log.user_id,
            "timestamp": log.timestamp.isoformat(),
            "details": log.details
        }
        for log in recent_logs
    ]

    return {
        "total_admins": total,
        "active_admins": active,
        "inactive_admins": inactive,
        "roles_distribution": roles_dist,
        "recent_activity": recent_activity
    }

@router.get("/users", response_model=List[UserResponse])
def list_users(
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin", "admin"]))
):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if search:
        search_fmt = f"%{search.lower()}%"
        query = query.filter(
            func.lower(User.full_name).like(search_fmt) |
            func.lower(User.username).like(search_fmt) |
            func.lower(User.email).like(search_fmt) |
            func.lower(User.district).like(search_fmt)
        )
    return query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()

@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin", "admin"]))
):
    # Only super_admin can create another super_admin
    if user_in.role == "super_admin" and current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a Super Admin can create accounts with the Super Admin role"
        )

    # Check username & email uniqueness
    if db.query(User).filter(User.username == user_in.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    new_user = User(
        username=user_in.username,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        full_name=user_in.full_name,
        role=user_in.role,
        department=user_in.department or "Revenue Department",
        state=user_in.state or "Uttar Pradesh",
        district=user_in.district or "Kanpur Nagar",
        tehsil=user_in.tehsil or "Bilhaur",
        is_active=user_in.is_active
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    audit_service.log_event(
        db,
        action="ADMIN_CREATED",
        user_id=current_user.id,
        details={
            "created_user_id": new_user.id,
            "created_username": new_user.username,
            "role": new_user.role,
            "created_by": current_user.username
        }
    )

    return new_user

@router.get("/users/{id}", response_model=UserResponse)
def get_user_by_id(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin", "admin"]))
):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/users/{id}", response_model=UserResponse)
def update_user(
    id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin", "admin"]))
):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prevent non-superadmin from promoting to or modifying super_admin
    if (user.role == "super_admin" or user_in.role == "super_admin") and current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a Super Admin can modify or assign the Super Admin role"
        )

    if user_in.email and user_in.email != user.email:
        if db.query(User).filter(User.email == user_in.email, User.id != id).first():
            raise HTTPException(status_code=400, detail="Email already in use by another account")
        user.email = user_in.email

    if user_in.full_name is not None:
        user.full_name = user_in.full_name
    if user_in.role is not None:
        user.role = user_in.role
    if user_in.department is not None:
        user.department = user_in.department
    if user_in.state is not None:
        user.state = user_in.state
    if user_in.district is not None:
        user.district = user_in.district
    if user_in.tehsil is not None:
        user.tehsil = user_in.tehsil
    if user_in.is_active is not None:
        user.is_active = user_in.is_active

    db.commit()
    db.refresh(user)

    audit_service.log_event(
        db,
        action="ADMIN_UPDATED",
        user_id=current_user.id,
        details={
            "updated_user_id": user.id,
            "username": user.username,
            "updated_by": current_user.username
        }
    )

    return user

@router.put("/users/{id}/status", response_model=UserResponse)
def update_user_status(
    id: int,
    status_in: UserStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin", "admin"]))
):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id and not status_in.is_active:
        raise HTTPException(status_code=400, detail="You cannot deactivate your own account")

    if user.role == "super_admin" and current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Cannot alter Super Admin status")

    user.is_active = status_in.is_active
    db.commit()
    db.refresh(user)

    action_name = "ADMIN_ACTIVATED" if user.is_active else "ADMIN_DEACTIVATED"
    audit_service.log_event(
        db,
        action=action_name,
        user_id=current_user.id,
        details={
            "target_user_id": user.id,
            "username": user.username,
            "new_status": user.is_active,
            "acted_by": current_user.username
        }
    )

    return user

@router.post("/users/{id}/reset-password")
def reset_user_password(
    id: int,
    reset_in: UserPasswordReset,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin", "admin"]))
):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role == "super_admin" and current_user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Only Super Admin can reset Super Admin password")

    if len(reset_in.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long")

    user.password_hash = get_password_hash(reset_in.new_password)
    db.commit()

    audit_service.log_event(
        db,
        action="PASSWORD_RESET",
        user_id=current_user.id,
        details={
            "target_user_id": user.id,
            "username": user.username,
            "reset_by": current_user.username
        }
    )

    return {"status": "success", "message": f"Password for '{user.username}' reset successfully"}

@router.delete("/users/{id}")
def delete_user(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["super_admin", "admin"]))
):
    user = db.query(User).filter(User.id == id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    if user.role == "super_admin":
        raise HTTPException(status_code=403, detail="Super Admin account cannot be deleted")

    deleted_username = user.username
    db.delete(user)
    db.commit()

    audit_service.log_event(
        db,
        action="ADMIN_DELETED",
        user_id=current_user.id,
        details={
            "deleted_user_id": id,
            "deleted_username": deleted_username,
            "deleted_by": current_user.username
        }
    )

    return {"status": "success", "message": f"User '{deleted_username}' removed successfully"}
