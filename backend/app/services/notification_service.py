from typing import Optional
from sqlalchemy.orm import Session
from app.models.audit import Notification

class NotificationService:
    def send(
        self,
        db: Session,
        title: str,
        message: str,
        user_id: Optional[int] = None,
        notif_type: str = "info",
        link: Optional[str] = None
    ) -> Notification:
        """Dispatches an in-app notification."""
        notif = Notification(
            user_id=user_id,
            title=title,
            message=message,
            type=notif_type,
            link=link
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        return notif

notification_service = NotificationService()
