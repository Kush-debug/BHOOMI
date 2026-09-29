from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from app.models.audit import AuditLog

class AuditService:
    def log_event(
        self,
        db: Session,
        action: str,
        user_id: Optional[int] = None,
        document_id: Optional[int] = None,
        record_id: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: str = "127.0.0.1"
    ) -> AuditLog:
        """Appends immutable event record to the audit trail."""
        log = AuditLog(
            user_id=user_id,
            document_id=document_id,
            record_id=record_id,
            action=action,
            details=details or {},
            ip_address=ip_address,
            timestamp=datetime.utcnow()
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

audit_service = AuditService()
