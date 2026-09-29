from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel

class ValidationResultResponse(BaseModel):
    id: int
    document_id: int
    record_id: Optional[int] = None
    validation_type: str
    rule_name: str
    severity: str
    status: str
    field_name: Optional[str] = None
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    message: str
    created_at: datetime

    class Config:
        from_attributes = True

class MasterLocationResponse(BaseModel):
    id: int
    state: str
    district: str
    tehsil: str
    village: str
    village_code: Optional[str] = None
    pincode: Optional[str] = None

    class Config:
        from_attributes = True
