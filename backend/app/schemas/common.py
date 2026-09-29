from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    document_id: Optional[int] = None
    record_id: Optional[int] = None
    action: str
    details: Dict[str, Any]
    ip_address: str
    timestamp: datetime

    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    title: str
    message: str
    type: str
    link: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

# DashboardStats was removed as a response_model: the dashboard endpoint now
# returns values that are legitimately absent (None = "not measured yet"), which a
# rigid non-optional schema cannot express without inventing defaults.
