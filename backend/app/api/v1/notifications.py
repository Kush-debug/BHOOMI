from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.auth.rbac import get_current_user
from app.models.user import User
from app.models.audit import Notification
from app.schemas.common import NotificationResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])

@router.get("/", response_model=List[NotificationResponse])
def get_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    # Users see only their own notifications.
    return (
        db.query(Notification)
        .filter((Notification.user_id == current_user.id) | (Notification.user_id.is_(None)))
        .order_by(Notification.created_at.desc())
        .limit(50)
        .all()
    )

@router.put("/{id}/read")
def mark_as_read(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notif = (
        db.query(Notification)
        .filter(
            Notification.id == id,
            (Notification.user_id == current_user.id) | (Notification.user_id.is_(None)),
        )
        .first()
    )
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"message": "Notification marked as read"}

@router.put("/read-all")
def mark_all_as_read(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    db.query(Notification).filter(Notification.user_id == current_user.id).update(
        {Notification.is_read: True}
    )
    db.commit()
    return {"message": "All notifications marked as read"}
